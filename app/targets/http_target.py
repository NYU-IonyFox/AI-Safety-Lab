import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HTTPTextTarget:
    """
    Generic HTTP adapter for the model under test.

    Supported endpoint shapes:
    1) OpenAI-compatible chat completions:
       POST /v1/chat/completions
       body: {"model": str, "messages": [{"role":"user","content":str}]}
       returns choices[0].message.content
    2) Generic JSON endpoint:
       POST <endpoint>
       body: {"prompt": str} (plus optional passthrough)
       returns first available field from ["answer","response","output","text"]
    """

    def __init__(self, timeout_sec: int = 60) -> None:
        self.timeout_sec = timeout_sec

    def complete_text(
        self,
        endpoint: str,
        prompt: str,
        api_key: str = "",
        model: str = "",
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        endpoint = endpoint.strip()
        if not endpoint:
            raise RuntimeError("target endpoint is empty")

        if endpoint.endswith("/v1/chat/completions") or endpoint.endswith("/chat/completions"):
            body: dict[str, Any] = {
                "model": model or "local-model",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            }
            if isinstance(extra_body, dict):
                body.update(extra_body)
            raw = self._post_json(endpoint, body=body, api_key=api_key)
            try:
                return str(raw["choices"][0]["message"]["content"])
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"invalid OpenAI-compatible response: {raw}") from e

        body = {"prompt": prompt}
        if isinstance(extra_body, dict):
            body.update(extra_body)
        raw = self._post_json(endpoint, body=body, api_key=api_key)
        for key in ("answer", "response", "output", "text"):
            if key in raw:
                return str(raw[key])
        if isinstance(raw, dict):
            return json.dumps(raw, ensure_ascii=False)
        return str(raw)

    def _post_json(self, endpoint: str, body: dict[str, Any], api_key: str = "") -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.timeout_sec) as response:
                raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"target HTTPError {e.code}: {detail}") from e
        except URLError as e:
            raise RuntimeError(f"target connection failed: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"target returned non-JSON response: {e}") from e
