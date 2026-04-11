from app.council import synthesize_council
from app.schemas import ExpertDetailPayload, ExpertVerdict



def make_verdict(name: str, *, status: str = "success", risk: float = 0.2, confidence: float = 0.8, critical: bool = False) -> ExpertVerdict:
    return ExpertVerdict(
        expert_name=name,
        evaluation_status=status,
        risk_score=risk,
        confidence=confidence,
        critical=critical,
        risk_tier="HIGH" if risk >= 0.65 else "MINIMAL",
        summary=f"{name} summary",
        findings=[],
        detail_payload=ExpertDetailPayload(evaluation_status=status),
        evidence={},
    )



def test_council_blocks_on_team1_and_team2_high_risk():
    result = synthesize_council(
        [
            make_verdict("team3_risk_expert", risk=0.30),
            make_verdict("team2_redteam_expert", risk=0.82),
            make_verdict("team1_policy_expert", risk=0.76),
        ]
    )
    assert result.decision == "REJECT"
    assert "team2_redteam_expert" in result.triggered_by
    assert "team1_policy_expert" in result.triggered_by



def test_council_reviews_on_failed_expert():
    result = synthesize_council(
        [
            make_verdict("team3_risk_expert", risk=0.20),
            make_verdict("team2_redteam_expert", status="failed", risk=0.50),
            make_verdict("team1_policy_expert", risk=0.20),
        ]
    )
    assert result.decision == "REVIEW"
    assert result.needs_human_review is True
    assert result.cross_expert_critique



def test_council_includes_cross_expert_critique_and_actions():
    result = synthesize_council(
        [
            make_verdict("team3_risk_expert", risk=0.68),
            make_verdict("team2_redteam_expert", risk=0.82),
            make_verdict("team1_policy_expert", risk=0.76),
        ]
    )
    assert result.decision == "REJECT"
    assert "Team1 and Team2 independently reached high-risk conclusions" in " ".join(result.cross_expert_critique)
    assert result.consensus_summary
    assert result.recommended_actions


def test_council_rejects_when_team3_and_another_expert_are_both_high_risk():
    result = synthesize_council(
        [
            make_verdict("team3_risk_expert", risk=0.85),
            make_verdict("team2_redteam_expert", risk=0.78),
            make_verdict("team1_policy_expert", risk=0.30),
        ]
    )
    assert result.decision == "REJECT"
    assert result.decision_rule_triggered == "multi_expert_high_risk"



def test_council_approves_low_risk_stable_outputs():
    result = synthesize_council(
        [
            make_verdict("team3_risk_expert", risk=0.18),
            make_verdict("team2_redteam_expert", risk=0.22),
            make_verdict("team1_policy_expert", risk=0.20),
        ]
    )
    assert result.decision == "APPROVE"
    assert result.needs_human_review is False
    assert result.consensus_summary
    assert result.cross_expert_critique
    assert result.recommended_actions
