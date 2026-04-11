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
