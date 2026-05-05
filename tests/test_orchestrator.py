"""
Phase 5 tests — SAFE orchestration pipeline (L3 Expert Council → L4 Arbitration).
All tests use EXECUTION_MODE=rules; no LLM is loaded.
"""
from __future__ import annotations

import os

os.environ["EXECUTION_MODE"] = "rules"

import pytest
from fastapi.testclient import TestClient

from app.orchestrator import run_evaluation, _adapt_for_arbitration, _build_recommendations
from app.safe_schemas import EvidenceBundle, SAFEEvaluationResponse, TranslationReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        input_type="conversation",
        translation_report=TranslationReport(
            translation_applied=False,
            primary_language="eng_Latn",
        ),
        content={"text": "Hello, this is a test input."},
    )


def _bundle_with_uncertainty() -> EvidenceBundle:
    return EvidenceBundle(
        input_type="document",
        translation_report=TranslationReport(
            translation_applied=True,
            primary_language="fra_Latn",
            confidence_numeric=0.72,
            confidence_warning=True,
        ),
        content={"text": "Bonjour, ceci est un test."},
    )


# ---------------------------------------------------------------------------
# 1. run_evaluation() returns SAFEEvaluationResponse
# ---------------------------------------------------------------------------

def test_run_evaluation_returns_safe_response():
    result = run_evaluation(_minimal_bundle())
    assert isinstance(result, SAFEEvaluationResponse)


def test_run_evaluation_returns_safe_response_with_uncertainty():
    result = run_evaluation(_bundle_with_uncertainty())
    assert isinstance(result, SAFEEvaluationResponse)


# ---------------------------------------------------------------------------
# 2. verdict is one of the three valid values
# ---------------------------------------------------------------------------

def test_run_evaluation_verdict_is_valid():
    result = run_evaluation(_minimal_bundle())
    assert result.verdict in ("APPROVE", "HOLD", "REJECT")


def test_run_evaluation_rules_mode_all_low_gives_approve():
    """In rules mode all experts return LOW → arbitration Rule 6 → APPROVE."""
    result = run_evaluation(_minimal_bundle())
    assert result.verdict == "APPROVE"


def test_run_evaluation_uncertainty_flag_triggers_hold():
    """confidence_warning=True → uncertainty_flag=True → arbitration Rule 3 → HOLD."""
    result = run_evaluation(_bundle_with_uncertainty())
    assert result.verdict == "HOLD"


# ---------------------------------------------------------------------------
# 3. experts list has exactly three entries
# ---------------------------------------------------------------------------

def test_run_evaluation_has_three_experts():
    result = run_evaluation(_minimal_bundle())
    assert len(result.experts) == 3


def test_run_evaluation_expert_ids_are_correct():
    result = run_evaluation(_minimal_bundle())
    ids = {e.id for e in result.experts}
    assert ids == {
        "expert_adversarial_security",
        "expert_content_safety",
        "expert_governance_un",
    }


def test_run_evaluation_experts_have_overall_field():
    result = run_evaluation(_minimal_bundle())
    for expert in result.experts:
        assert expert.overall in ("HIGH", "MEDIUM", "LOW")


# ---------------------------------------------------------------------------
# 4. primary_reason contains "rule" key
# ---------------------------------------------------------------------------

def test_run_evaluation_primary_reason_has_rule_key():
    result = run_evaluation(_minimal_bundle())
    assert "rule" in result.primary_reason


def test_run_evaluation_primary_reason_has_expert_summary():
    result = run_evaluation(_minimal_bundle())
    assert "expert_summary" in result.primary_reason


def test_run_evaluation_rule_string_is_nonempty():
    result = run_evaluation(_minimal_bundle())
    assert isinstance(result.primary_reason["rule"], str)
    assert len(result.primary_reason["rule"]) > 0


# ---------------------------------------------------------------------------
# 5. recommendations is a list
# ---------------------------------------------------------------------------

def test_run_evaluation_recommendations_is_list():
    result = run_evaluation(_minimal_bundle())
    assert isinstance(result.recommendations, list)


def test_run_evaluation_rules_mode_no_recommendations():
    """In rules mode all experts return LOW → no triggered dims → no recommendations."""
    result = run_evaluation(_minimal_bundle())
    assert result.recommendations == []


# ---------------------------------------------------------------------------
# 6. _adapt_for_arbitration() correctness
# ---------------------------------------------------------------------------

def test_adapt_maps_id_to_short_form():
    expert_dict = {
        "id": "expert_adversarial_security",
        "overall": "HIGH",
        "triggered_dimensions": [
            {"name": "jailbreak_resistance", "tier": "CORE", "level": "HIGH",
             "evidence_quality": "Strong", "regulatory_anchor": "OWASP LLM01:2025", "reason": "x"}
        ],
    }
    adapted = _adapt_for_arbitration(expert_dict)
    assert adapted["expert_id"] == "expert_1"
    assert adapted["expert_risk_level"] == "HIGH"


def test_adapt_maps_tier_and_level():
    expert_dict = {
        "id": "expert_content_safety",
        "overall": "MEDIUM",
        "triggered_dimensions": [
            {"name": "sensitive_data_leakage", "tier": "CORE", "level": "MEDIUM",
             "evidence_quality": "Partial", "regulatory_anchor": "OWASP LLM02:2025", "reason": "y"}
        ],
    }
    adapted = _adapt_for_arbitration(expert_dict)
    assert adapted["expert_id"] == "expert_2"
    scores = adapted["dimension_scores"]
    assert len(scores) == 1
    assert scores[0]["criticality"] == "CORE"
    assert scores[0]["severity"] == "MEDIUM"


def test_adapt_empty_triggered_dimensions():
    expert_dict = {"id": "expert_governance_un", "overall": "LOW", "triggered_dimensions": []}
    adapted = _adapt_for_arbitration(expert_dict)
    assert adapted["expert_id"] == "expert_3"
    assert adapted["dimension_scores"] == []


# ---------------------------------------------------------------------------
# 7. POST /evaluate endpoint returns 200
# ---------------------------------------------------------------------------

def test_post_evaluate_returns_200():
    from app.main import app
    client = TestClient(app)
    payload = {
        "input_type": "conversation",
        "translation_report": {
            "translation_applied": False,
            "primary_language": "eng_Latn",
        },
        "content": {"text": "test"},
    }
    response = client.post("/evaluate", json=payload)
    assert response.status_code == 200


def test_post_evaluate_returns_valid_verdict():
    from app.main import app
    client = TestClient(app)
    payload = {
        "input_type": "conversation",
        "translation_report": {
            "translation_applied": False,
            "primary_language": "eng_Latn",
        },
    }
    response = client.post("/evaluate", json=payload)
    body = response.json()
    assert body["verdict"] in ("APPROVE", "HOLD", "REJECT")


def test_post_evaluate_body_has_required_fields():
    from app.main import app
    client = TestClient(app)
    payload = {
        "input_type": "document",
        "translation_report": {
            "translation_applied": False,
            "primary_language": "eng_Latn",
        },
    }
    response = client.post("/evaluate", json=payload)
    body = response.json()
    for field in ("evaluation_id", "verdict", "experts", "recommendations", "primary_reason"):
        assert field in body, f"Missing field: {field}"


def test_health_endpoint_unchanged():
    from app.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
