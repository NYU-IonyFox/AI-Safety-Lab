from app.experts import Team3RiskExpert
from app.schemas import AgentContext, EvaluationRequest


def test_team3_low_impact_case_does_not_fail_closed_when_no_protocols_are_active() -> None:
    expert = Team3RiskExpert()
    request = EvaluationRequest(
        context=AgentContext(agent_name="low-impact-demo", domain="Other", capabilities=[], high_autonomy=False),
        conversation=[],
        metadata={},
        selected_policies=["eu_ai_act"],
    )

    result = expert.assess(request)

    assert result.risk_tier == "TIER_1"
    assert result.risk_score < 0.3
    assert result.critical is False
    assert "low baseline deployment exposure" in result.summary.lower()
    assert result.detail_payload.protocol_results == []


def test_team3_normalizes_complete_slm_verdict_to_success() -> None:
    expert = Team3RiskExpert()

    result = {
        "risk_score": 0.78,
        "confidence": 0.92,
        "critical": False,
        "risk_tier": "TIER_3",
        "summary": "Repository exposes an unauthenticated upload pipeline connected to external AI services.",
        "findings": ["User-controlled uploads and external AI processing expand deployment exposure."],
        "evaluation_status": "degraded",
    }

    assert expert._normalize_slm_status(result) == "success"


def test_team3_preserves_failed_when_model_cannot_complete_review() -> None:
    expert = Team3RiskExpert()

    result = {
        "risk_score": 0.0,
        "confidence": 0.0,
        "critical": False,
        "risk_tier": "TIER_1",
        "summary": "Unable to evaluate because the payload is incomplete.",
        "findings": ["Input malformed for system-risk evaluation."],
        "evaluation_status": "failed",
    }

    assert expert._normalize_slm_status(result) == "failed"
