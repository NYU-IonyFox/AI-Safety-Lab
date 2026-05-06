from __future__ import annotations

import json
import os
from pathlib import Path

from app.anchors.anchor_loader import build_anchor_table, load_anchors
from app.experts.base import BaseExpert, compute_overall

_DIMENSIONS = [
    {"name": "harmful_content_generation",  "tier": "CORE"},
    {"name": "sensitive_data_leakage",       "tier": "CORE"},
    {"name": "bias_fairness",               "tier": "IMPORTANT"},
    {"name": "hallucination_misinformation", "tier": "IMPORTANT"},
    {"name": "manipulation_deception",       "tier": "IMPORTANT"},
    {"name": "legal_data_compliance",        "tier": "CORE"},
    {"name": "secret_credential_exposure",   "tier": "IMPORTANT"},
]

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "model_assets" / "prompts" / "expert_2_system_prompt.txt"
)
_ANCHORS_PATH = (
    Path(__file__).resolve().parent.parent / "anchors" / "framework_anchors_v2.json"
)


class ContentSafetyExpert(BaseExpert):
    expert_id = "expert_content_safety"
    dimensions = _DIMENSIONS

    def assess(self, evidence_bundle: dict, api_key: str = "") -> dict:
        self._api_key = api_key
        if self.execution_mode() == "rules":
            result = self._mock_result()
        else:
            result = self._assess_llm(evidence_bundle)
        print(f"[{self.expert_id}] overall={result['overall']}, triggered={len(result.get('triggered_dimensions', []))}")
        return result

    def _assess_llm(self, evidence_bundle: dict) -> dict:
        system_prompt = self._build_system_prompt()
        items = self._call_llm(system_prompt, evidence_bundle)
        return self._parse_response(items)

    def _build_system_prompt(self) -> str:
        with open(_PROMPT_PATH, encoding="utf-8") as f:
            prompt = f.read()
        anchors = load_anchors(str(_ANCHORS_PATH))
        table = build_anchor_table(self.expert_id, anchors)
        return prompt.replace("{{anchor_table}}", table)

    def _call_llm(self, system_prompt: str, evidence_bundle: dict) -> list:
        api_key = (
            getattr(self, "_api_key", "")
            or os.getenv("ANTHROPIC_API_KEY", "")
        )
        user_content = self._build_user_content(evidence_bundle)
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("anthropic package required for llm_api mode") from exc
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return self._parse_llm_raw(msg.content[0].text)

    def _parse_response(self, items: list) -> dict:
        dim_tier = {d["name"]: d["tier"] for d in self.dimensions}
        all_scores = [
            {"tier": dim_tier.get(item.get("name", ""), "IMPORTANT"), "level": item.get("level", "LOW")}
            for item in items
            if isinstance(item, dict)
        ]
        triggered = [
            {
                "name": item["name"],
                "tier": dim_tier.get(item["name"], "IMPORTANT"),
                "level": item["level"],
                "evidence_quality": item.get("evidence_quality", "Partial"),
                "regulatory_anchor": item.get("regulatory_anchor", ""),
                "reason": item.get("reason", ""),
            }
            for item in items
            if isinstance(item, dict) and item.get("level", "LOW") != "LOW" and "name" in item
        ]
        return {
            "id": self.expert_id,
            "overall": compute_overall(all_scores),
            "triggered_dimensions": triggered,
        }
