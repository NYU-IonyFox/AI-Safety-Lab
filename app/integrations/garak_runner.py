import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.config import GARAK_COMMAND_TEMPLATE, GARAK_TIMEOUT_SEC, GARAK_WORKDIR
from app.schemas import EvaluationRequest


class GarakRunner:
    """
    Command-template adapter for garak scanning chain.

    Required env:
      GARAK_COMMAND_TEMPLATE
    Placeholders:
      {input_json}, {output_json}
    """

    def __init__(
        self,
        command_template: str | None = None,
        timeout_sec: int | None = None,
        workdir: str | None = None,
    ) -> None:
        self.command_template = command_template if command_template is not None else GARAK_COMMAND_TEMPLATE
        self.timeout_sec = timeout_sec if timeout_sec is not None else GARAK_TIMEOUT_SEC
        self.workdir = Path(workdir if workdir is not None else GARAK_WORKDIR)

    def scan(self, request: EvaluationRequest) -> dict[str, Any]:
        if not self.command_template:
            raise RuntimeError("GARAK_COMMAND_TEMPLATE is not configured")

        with TemporaryDirectory(prefix="garak_scan_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            input_json = tmpdir_path / "input.json"
            output_json = tmpdir_path / "output.json"
            input_json.write_text(
                json.dumps(self._to_garak_input(request), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            cmd = self.command_template.format(
                input_json=str(input_json),
                output_json=str(output_json),
            )
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Garak command failed (exit={proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
                )

            raw = self._read_result(output_json, proc.stdout)
            return self._normalize_result(raw)

    def _to_garak_input(self, request: EvaluationRequest) -> dict[str, Any]:
        return {
            "agent_context": request.context.model_dump(),
            "selected_policies": request.selected_policies,
            "conversation": [t.model_dump() for t in request.conversation],
            "metadata": request.metadata,
        }

    def _read_result(self, output_json: Path, stdout: str) -> dict[str, Any]:
        if output_json.exists():
            return json.loads(output_json.read_text(encoding="utf-8"))
        out = stdout.strip()
        if out:
            return json.loads(out)
        raise RuntimeError("Garak command produced no JSON output")

    def _normalize_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        findings = self._extract_findings(raw)
        severity = self._extract_severity(raw, findings)
        confidence = float(raw.get("confidence", 0.72))
        if severity >= 0.85:
            risk_tier = "HIGH"
            critical = True
        elif severity >= 0.6:
            risk_tier = "LIMITED"
            critical = False
        else:
            risk_tier = "MINIMAL"
            critical = False

        return {
            "risk_score": max(0.0, min(1.0, severity)),
            "confidence": max(0.0, min(1.0, confidence)),
            "critical": critical,
            "risk_tier": risk_tier,
            "summary": str(raw.get("summary", "Garak scan completed")),
            "findings": findings,
            "raw": raw,
        }

    def _extract_findings(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        # Accept common shapes:
        # 1) {"findings":[...]}
        # 2) {"records":[...]}
        # 3) {"results":[...]}
        for key in ("findings", "records", "results"):
            value = raw.get(key)
            if isinstance(value, list):
                normalized = []
                for item in value:
                    if not isinstance(item, dict):
                        normalized.append({"name": str(item), "severity": 0.5, "policy_tags": []})
                        continue
                    normalized.append(
                        {
                            "name": str(item.get("name") or item.get("probe") or item.get("id") or "unknown"),
                            "severity": float(item.get("severity", item.get("score", 0.5))),
                            "policy_tags": item.get("policy_tags", []),
                            "status": item.get("status", "detected"),
                        }
                    )
                return normalized
        return []

    def _extract_severity(self, raw: dict[str, Any], findings: list[dict[str, Any]]) -> float:
        if isinstance(raw.get("risk_score"), (int, float)):
            return float(raw["risk_score"])
        if findings:
            return sum(float(f.get("severity", 0.5)) for f in findings) / len(findings)
        return 0.25

