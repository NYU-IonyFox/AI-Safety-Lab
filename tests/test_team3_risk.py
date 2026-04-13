import pytest

from app.deliberation import _coerce_risk_tier
from app.experts import Team3RiskExpert
from app.schemas import AgentContext, EvaluationRequest, ExpertDetailPayload, ExpertVerdict

VALID_TIERS = {"MINIMAL", "LIMITED", "HIGH", "UNACCEPTABLE"}
BANNED_TIERS = {"TIER_1", "TIER_2", "TIER_3", "TIER_4"}


def _make_request(domain: str = "Other", capabilities: list | None = None, high_autonomy: bool = False) -> EvaluationRequest:
    return EvaluationRequest(
        context=AgentContext(
            agent_name="test-agent",
            domain=domain,
            capabilities=capabilities or [],
            high_autonomy=high_autonomy,
        ),
        conversation=[],
        metadata={},
        selected_policies=["eu_ai_act"],
    )


def test_team3_low_impact_case_does_not_fail_closed_when_no_protocols_are_active() -> None:
    expert = Team3RiskExpert()
    request = _make_request()

    result = expert.assess(request)

    assert result.risk_tier == "MINIMAL"
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
        "risk_tier": "HIGH",
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
        "risk_tier": "MINIMAL",
        "summary": "Unable to evaluate because the payload is incomplete.",
        "findings": ["Input malformed for system-risk evaluation."],
        "evaluation_status": "failed",
    }

    assert expert._normalize_slm_status(result) == "failed"


@pytest.mark.parametrize(
    "domain,capabilities,high_autonomy",
    [
        ("Other", [], False),
        ("Education", [], False),
        ("Education", ["decision_making"], True),
        ("Social Scoring", [], False),
    ],
)
def test_team3_risk_tier_is_always_canonical_label(domain: str, capabilities: list, high_autonomy: bool) -> None:
    expert = Team3RiskExpert()
    request = _make_request(domain=domain, capabilities=capabilities, high_autonomy=high_autonomy)

    result = expert.assess(request)

    assert result.risk_tier in VALID_TIERS, f"Got unexpected tier: {result.risk_tier!r}"
    assert result.risk_tier not in BANNED_TIERS


def test_team3_rule_baseline_never_produces_tier_x_labels() -> None:
    expert = Team3RiskExpert()
    for domain in ["Other", "Education", "Law Enforcement", "Social Scoring"]:
        request = _make_request(domain=domain)
        baseline = expert._evaluate_rule_baseline(request)
        tier = baseline["risk_tier"]
        assert tier in VALID_TIERS, f"_evaluate_rule_baseline returned {tier!r} for domain={domain!r}"
        assert tier not in BANNED_TIERS


def _make_verdict_for_coerce(risk_tier: str, risk_score: float) -> ExpertVerdict:
    return ExpertVerdict(
        expert_name="test",
        evaluation_status="success",
        risk_score=risk_score,
        confidence=0.7,
        critical=False,
        risk_tier=risk_tier,
        summary="test",
        findings=[],
        detail_payload=ExpertDetailPayload(),
        evidence={},
    )


@pytest.mark.parametrize(
    "risk_score,expected_tier",
    [
        (0.90, "UNACCEPTABLE"),
        (0.85, "UNACCEPTABLE"),
        (0.80, "HIGH"),
        (0.65, "HIGH"),
        (0.60, "LIMITED"),
        (0.45, "LIMITED"),
        (0.30, "MINIMAL"),
        (0.00, "MINIMAL"),
    ],
)
def test_coerce_risk_tier_returns_canonical_labels(risk_score: float, expected_tier: str) -> None:
    verdict = _make_verdict_for_coerce("HIGH", risk_score)
    result = _coerce_risk_tier(verdict, risk_score)
    assert result == expected_tier
    assert result in VALID_TIERS
    assert result not in BANNED_TIERS


@pytest.mark.parametrize("tier_x", ["TIER_1", "TIER_2", "TIER_3", "TIER_4"])
def test_coerce_risk_tier_never_returns_tier_x_even_when_passed_one(tier_x: str) -> None:
    verdict = _make_verdict_for_coerce(tier_x, 0.70)
    result = _coerce_risk_tier(verdict, 0.70)
    assert result not in BANNED_TIERS
    assert result in VALID_TIERS
