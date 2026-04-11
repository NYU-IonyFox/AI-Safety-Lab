from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.slm.base import SLMRunner


class LocalHTTPRunner(SLMRunner):
    """
    Local SLM runner over HTTP.

    Stable request contract:
      POST <complete-json endpoint>
      body: {"task": str, "payload": object}

    The runner also probes /health and /version when available so it can
    normalize version-specific local shim responses.
    """

    def __init__(self) -> None:
        self.endpoint = os.getenv("LOCAL_SLM_ENDPOINT", "").strip()
        self.timeout_sec = float(os.getenv("LOCAL_SLM_TIMEOUT_SEC", "60"))
        self.api_key = os.getenv("LOCAL_SLM_API_KEY", "").strip()
        self._complete_json_endpoint = self._normalize_complete_json_endpoint(self.endpoint)
        self._service_info: dict[str, Any] = {}

    def complete_json(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._complete_json_endpoint:
            raise RuntimeError("LOCAL_SLM_ENDPOINT is required when SLM_BACKEND=local")

        self._refresh_service_info()
        raw = self._post_json(self._complete_json_endpoint, {"task": task, "payload": payload})

        if isinstance(raw, dict) and isinstance(raw.get("result"), dict):
            result = raw["result"]
        elif isinstance(raw, dict):
            result = raw
        else:
            raise RuntimeError("Local SLM response is not a JSON object")

        return self._normalize_result(result)

    def _refresh_service_info(self) -> None:
        if self._service_info:
            return

        base_endpoint = self._base_endpoint(self._complete_json_endpoint)
        info: dict[str, Any] = {"endpoint": self._complete_json_endpoint, "base_endpoint": base_endpoint}
        for suffix in ("/health", "/version"):
            try:
                probe = self._get_json(f"{base_endpoint}{suffix}")
            except Exception:  # noqa: BLE001
                continue
            if isinstance(probe, dict):
                info.update(probe)
        self._service_info = info

    def _normalize_complete_json_endpoint(self, endpoint: str) -> str:
        endpoint = endpoint.strip().rstrip("/")
        if not endpoint:
            return ""

        if endpoint.endswith(("/v1/complete-json", "/complete-json")):
            return endpoint
        if endpoint.endswith(("/health", "/version")):
            endpoint = endpoint.rsplit("/", 1)[0]
        return f"{endpoint}/v1/complete-json"

    def _base_endpoint(self, endpoint: str) -> str:
        endpoint = endpoint.strip().rstrip("/")
        if not endpoint:
            return ""
        if endpoint.endswith("/v1/complete-json"):
            return endpoint[: -len("/v1/complete-json")]
        if endpoint.endswith("/complete-json"):
            return endpoint[: -len("/complete-json")]
        return endpoint

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout_sec) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except HTTPError as e:
            content = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Local SLM HTTPError {e.code}: {content}") from e
        except URLError as e:
            raise RuntimeError(f"Local SLM connection failed: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Local SLM returned invalid JSON: {e}") from e

    def _get_json(self, url: str) -> dict[str, Any]:
        req = Request(url, method="GET")
        try:
            with urlopen(req, timeout=self.timeout_sec) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except HTTPError as e:
            content = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Local SLM HTTPError {e.code}: {content}") from e
        except URLError as e:
            raise RuntimeError(f"Local SLM connection failed: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Local SLM returned invalid JSON: {e}") from e

    def _normalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(result)
        service_version = str(self._service_info.get("version", normalized.get("service_version", "")))
        normalized["service_version"] = service_version
        normalized["service_name"] = str(self._service_info.get("service", self._service_info.get("name", "local")))

        verdict = normalized.get("verdict")
        if isinstance(verdict, dict):
            for key, value in verdict.items():
                normalized.setdefault(key, value)

        detail_payload = normalized.get("detail_payload")
        if not isinstance(detail_payload, dict):
            for key in ("detail", "details", "payload"):
                candidate = normalized.get(key)
                if isinstance(candidate, dict):
                    detail_payload = candidate
                    break
        if isinstance(detail_payload, dict):
            normalized["detail_payload"] = detail_payload

        normalized["risk_score"] = self._coerce_float(
            normalized,
            ["risk_score", "score", "severity", "confidence_score"],
            default=0.5,
        )
        normalized["confidence"] = self._coerce_float(normalized, ["confidence", "certainty"], default=0.5)
        normalized["critical"] = bool(normalized.get("critical", False))
        normalized["risk_tier"] = self._coerce_risk_tier(normalized, service_version)
        normalized["evaluation_status"] = self._coerce_evaluation_status(normalized)
        normalized["summary"] = str(normalized.get("summary", "Local SLM result"))

        findings = normalized.get("findings", [])
        if not isinstance(findings, list):
            findings = [str(findings)]
        normalized["findings"] = [str(f) for f in findings]
        normalized.setdefault("evidence", {})
        if isinstance(normalized["evidence"], dict):
            normalized["evidence"].setdefault("service_info", self._service_info)
        else:
            normalized["evidence"] = {"service_info": self._service_info}
        return normalized

    def _coerce_float(self, data: dict[str, Any], keys: list[str], default: float) -> float:
        for key in keys:
            raw = data.get(key)
            if isinstance(raw, (int, float)):
                value = float(raw)
                if value > 1.0 and key in {"score", "severity", "confidence_score"}:
                    if value > 5.0:
                        value = value / 100.0
                    else:
                        value = value / 5.0
                return max(0.0, min(1.0, value))
        return default

    def _coerce_risk_tier(self, data: dict[str, Any], service_version: str) -> str:
        risk_tier = str(data.get("risk_tier", "UNKNOWN"))
        if risk_tier != "UNKNOWN":
            return risk_tier

        risk_score = float(data.get("risk_score", 0.5))
        if service_version.lower().startswith("gamma4") and risk_score >= 0.85:
            return "UNACCEPTABLE"
        if risk_score >= 0.85:
            return "UNACCEPTABLE"
        if risk_score >= 0.65:
            return "HIGH"
        if risk_score >= 0.4:
            return "LIMITED"
        return "MINIMAL"

    def _coerce_evaluation_status(self, data: dict[str, Any]) -> str:
        status = str(data.get("evaluation_status", data.get("status", "success"))).lower()
        if status in {"success", "degraded", "failed"}:
            return status
        if status in {"ok", "pass", "passed"}:
            return "success"
        if status in {"warn", "warning", "partial"}:
            return "degraded"
        if status in {"error", "fail", "failed"}:
            return "failed"
        return "success"
