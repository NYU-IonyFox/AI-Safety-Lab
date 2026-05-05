from __future__ import annotations

from importlib.resources import files
from typing import Any


PROMPT_FILES = {
    "team1_policy_expert": "team1_policy_expert.txt",
    "team2_redteam_expert": "team2_redteam_expert.txt",
    "team3_risk_expert": "team3_risk_expert.txt",
}

LEGACY_PROMPT_FILES = {
    "team1_policy_expert": "expert_3_system_prompt.txt",
    "team2_redteam_expert": "expert_1_system_prompt.txt",
    "team3_risk_expert": "expert_2_system_prompt.txt",
}

RESPONSE_CONTRACTS: dict[str, dict[str, Any]] = {
    "team1_policy_expert": {
        "required": ["risk_score", "confidence", "critical", "risk_tier", "summary", "findings", "evaluation_status"],
        "optional": ["policy_alerts", "violations"],
        "notes": "Risk score must be 0..1. Use HIGH/LIMITED/MINIMAL style tiers for policy review.",
    },
    "team2_redteam_expert": {
        "required": ["risk_score", "confidence", "critical", "risk_tier", "summary", "findings", "evaluation_status"],
        "optional": ["dimension_scores", "protocol_results"],
        "notes": "Risk tier should reflect adversarial misuse severity and stay aligned with OWASP/MITRE style reasoning.",
    },
    "team3_risk_expert": {
        "required": ["risk_score", "confidence", "critical", "risk_tier", "summary", "findings", "evaluation_status"],
        "optional": ["protocol_results", "rule_baseline"],
        "notes": "Risk tier should use the TIER_1..TIER_4 style when possible for deployment/system review.",
    },
}


def load_expert_system_prompt(expert_name: str) -> str:
    prompt_dir = files("model_assets").joinpath("prompts")
    for filename in (PROMPT_FILES.get(expert_name, ""), LEGACY_PROMPT_FILES.get(expert_name, "")):
        if not filename:
            continue
        candidate = prompt_dir.joinpath(filename)
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return ""


def response_contract_for(expert_name: str) -> dict[str, Any]:
    return dict(RESPONSE_CONTRACTS.get(expert_name, RESPONSE_CONTRACTS["team1_policy_expert"]))
