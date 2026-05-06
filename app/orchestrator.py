from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from app.experts.expert_adversarial import AdversarialSecurityExpert
from app.experts.expert_content import ContentSafetyExpert
from app.experts.expert_governance import GovernanceExpert
from model_assets.council.arbitration import run_arbitration
from app.safe_schemas import (
    DimensionScore,
    EvidenceBundle,
    ExpertOutput,
    SAFEEvaluationResponse,
)
from app.safe_config import SAFE_VERSION
from app.reporting.report_service import generate_reports

# Maps new expert id → short id expected by arbitration.py
_EXPERT_ID_MAP: dict[str, str] = {
    "expert_adversarial_security": "expert_1",
    "expert_content_safety": "expert_2",
    "expert_governance_un": "expert_3",
}

# Maps snake_case dimension names → display names used in convergent risk detection
_DISPLAY_NAME_MAP: dict[str, str] = {
    "jailbreak_resistance": "Jailbreak Resistance",
    "prompt_injection_robustness": "Prompt Injection Robustness",
    "multilingual_jailbreak": "Multilingual Jailbreak",
    "multi_turn_stability": "Multi-turn Stability",
    "tool_agent_manipulation": "Tool/Agent Manipulation",
    "tier1_attack_surface": "Tier 1 Attack Surface",
    "tier2_injection_escalation": "Tier 2 Injection Escalation",
    "tier3_chain_attack": "Tier 3 Chain Attack",
    "harmful_content_generation": "Harmful Content Generation",
    "sensitive_data_leakage": "Sensitive Data Leakage",
    "bias_fairness": "Bias & Fairness",
    "hallucination_misinformation": "Hallucination & Misinformation",
    "manipulation_deception": "Manipulation / Deception",
    "legal_data_compliance": "Legal Data Compliance",
    "secret_credential_exposure": "Secret & Credential Exposure",
    "regulatory_compliance": "Regulatory Compliance",
    "global_equity_accessibility": "Global Equity & Accessibility",
    "political_conflict_neutrality": "Political Conflict Neutrality",
    "transparency_explainability": "Transparency & Explainability",
    "human_oversight_compatibility": "Human Oversight Compatibility",
    "prohibited_domain_deployment": "Prohibited Domain Deployment",
    "high_risk_domain_governance": "High-Risk Domain Governance",
    "auth_access_control": "Auth & Access Control",
}

# Maps arbitration.py final_decision values → SAFEEvaluationResponse verdict
_VERDICT_MAP: dict[str, str] = {
    "REJECT": "REJECT",
    "HOLD": "HOLD",
    "CONDITIONAL": "HOLD",
    "PASS": "APPROVE",
}


def _adapt_for_arbitration(expert_output: dict) -> dict:
    """Convert new Expert assess() output to the format expected by arbitration.py."""
    return {
        "expert_id": _EXPERT_ID_MAP.get(expert_output.get("id", ""), "unknown"),
        "expert_risk_level": expert_output.get("overall", "LOW"),
        "dimension_scores": [
            {
                "dimension": _DISPLAY_NAME_MAP.get(d["name"], d["name"]),
                "criticality": d["tier"],
                "severity": d["level"],
            }
            for d in expert_output.get("triggered_dimensions", [])
        ],
    }


def _make_expert_output(expert_dict: dict) -> ExpertOutput:
    """Convert a raw Expert assess() dict to a validated ExpertOutput model."""
    triggered = []
    for d in expert_dict.get("triggered_dimensions", []):
        eq = d.get("evidence_quality", "Partial")
        if eq not in ("Strong", "Partial", "Weak"):
            eq = "Partial"
        triggered.append(
            DimensionScore(
                name=d["name"],
                display_name=_DISPLAY_NAME_MAP.get(d["name"], d["name"]),
                tier=d["tier"],
                level=d["level"],
                evidence_quality=eq,
                regulatory_anchor=d.get("regulatory_anchor", ""),
                reason=d.get("reason", ""),
            )
        )
    return ExpertOutput(
        id=expert_dict["id"],
        overall=expert_dict["overall"],
        triggered_dimensions=triggered,
    )


def _build_recommendations(expert_outputs: list[dict]) -> list[dict]:
    """Generate one recommendation per triggered HIGH/MEDIUM dimension."""
    recs = []
    for expert in expert_outputs:
        for dim in expert.get("triggered_dimensions", []):
            if dim.get("level") in ("HIGH", "MEDIUM"):
                recs.append(
                    {
                        "text": (
                            f"Review and remediate "
                            f"{_DISPLAY_NAME_MAP.get(dim['name'], dim['name'])} "
                            f"risks before deployment."
                        ),
                        "source_expert": expert["id"],
                        "source_dimension": dim["name"],
                    }
                )
    return recs


def run_evaluation(evidence_bundle: EvidenceBundle) -> SAFEEvaluationResponse:
    """Run the full SAFE evaluation pipeline (L3 → L4) and return a response.

    Fail-closed: any unhandled exception returns a HOLD verdict.
    """
    try:
        bundle_dict = evidence_bundle.model_dump()

        # L3 — Expert Council
        print(f"[run_evaluation] Starting Expert Council. bundle.input_type={bundle_dict.get('input_type')}")
        result_1 = AdversarialSecurityExpert().assess(bundle_dict)
        print(f"[run_evaluation] Expert 1 done")
        result_2 = ContentSafetyExpert().assess(bundle_dict)
        print(f"[run_evaluation] Expert 2 done")
        result_3 = GovernanceExpert().assess(bundle_dict)
        print(f"[run_evaluation] Expert 3 done")

        # L4 — Arbitration (adapter converts Expert format → arbitration format)
        arb_inputs = [
            _adapt_for_arbitration(result_1),
            _adapt_for_arbitration(result_2),
            _adapt_for_arbitration(result_3),
        ]
        uncertainty_flag = bool(evidence_bundle.translation_report.confidence_warning)
        arb = run_arbitration(arb_inputs, uncertainty_flag)

        verdict: str = _VERDICT_MAP.get(arb.get("final_decision", "HOLD"), "HOLD")

        additional: list[str] = []
        if arb.get("convergent_risk_note"):
            additional.append(arb["convergent_risk_note"])

        safe_response = SAFEEvaluationResponse(
            evaluation_id=str(_uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            safe_version=SAFE_VERSION,
            verdict=verdict,
            primary_reason={
                "rule": arb.get("decision_rule_triggered", ""),
                "expert_summary": arb.get("expert_summary", {}),
            },
            additional_findings=additional,
            submission_context={"input_type": evidence_bundle.input_type},
            experts=[
                _make_expert_output(result_1),
                _make_expert_output(result_2),
                _make_expert_output(result_3),
            ],
            recommendations=_build_recommendations([result_1, result_2, result_3]),
            translation_report=evidence_bundle.translation_report,
            report_path="",
        )

        # L5 — Output (PDF + JSON); fail-closed: never crash the evaluation on report errors
        try:
            paths = generate_reports(safe_response)
            safe_response = safe_response.model_copy(update={"report_path": paths["pdf_path"]})
        except Exception:  # noqa: BLE001
            pass  # report_path stays ""

        return safe_response

    except Exception as _e:  # noqa: BLE001
        import traceback
        print(f"[run_evaluation ERROR] {_e}")
        traceback.print_exc()
        from app.safe_schemas import TranslationReport
        tr = getattr(evidence_bundle, "translation_report", None) or TranslationReport(
            translation_applied=False, primary_language="unknown"
        )
        return SAFEEvaluationResponse(
            evaluation_id=str(_uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            safe_version=SAFE_VERSION,
            verdict="HOLD",
            primary_reason={"rule": "pipeline_error"},
            additional_findings=["Evaluation pipeline encountered an error; HOLD applied (fail-closed)."],
            submission_context={},
            experts=[],
            recommendations=[],
            translation_report=tr,
            report_path="",
        )
