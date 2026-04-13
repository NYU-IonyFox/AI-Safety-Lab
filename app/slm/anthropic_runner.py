"""
app/slm/anthropic_runner.py

AnthropicRunner — calls the Anthropic API (Claude) as the SLM backend.

Usage: set SLM_BACKEND=anthropic in .env or environment.
Required env vars:
  ANTHROPIC_API_KEY   — Anthropic API key (mandatory at call time)
  ANTHROPIC_MODEL     — model ID (default: claude-haiku-4-5-20251001)
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from app.slm.base import SLMRunner

logger = logging.getLogger(__name__)


class AnthropicRunner(SLMRunner):
    """SLMRunner that delegates inference to the Anthropic Messages API."""

    backend_name = "anthropic"

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it in .env or as an environment variable before using "
                "SLM_BACKEND=anthropic."
            )
        self._api_key = api_key
        self._model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001").strip()

    def complete_json(
        self,
        task: str,
        payload: dict[str, Any],
        *,
        system_prompt: str = "",
        response_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import anthropic  # local import — only loaded when this backend is active

        user_content = json.dumps(payload, ensure_ascii=False)
        if response_contract:
            user_content += (
                "\n\nRespond with a JSON object that matches this schema:\n"
                + json.dumps(response_contract, ensure_ascii=False)
            )

        create_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": user_content}],
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            message = client.messages.create(**create_kwargs)
            raw_output = message.content[0].text
        except Exception as exc:
            logger.error("Anthropic API error for task %r: %s", task, exc)
            raise

        cleaned = self._clean_json(raw_output)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse failure for task %r (model=%s): %s\nRaw output: %.500s",
                task,
                self._model,
                exc,
                raw_output,
            )
            raise

    @staticmethod
    def _clean_json(raw: str) -> str:
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return raw.strip()

    def describe(self) -> dict[str, str]:
        return {"backend": self.backend_name, "model": self._model}
