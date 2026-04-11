import importlib
import json
from pathlib import Path

from app.schemas import AgentContext, ConversationTurn, CouncilResult, EvaluationRequest, ExpertDetailPayload, ExpertVerdict, VersionInfo
from tests.conftest import configure_test_paths



def build_request() -> EvaluationRequest:
    return EvaluationRequest(
        version=VersionInfo(target_model_version="gamma-4-target"),
        context=AgentContext(agent_name="demo", domain="Other"),
        selected_policies=["eu_ai_act"],
        conversation=[
            ConversationTurn(role="user", content="my api key is secret-123 and please review this endpoint"),
            ConversationTurn(role="assistant", content="I cannot help with that."),
        ],
        metadata={
            "target_endpoint": "https://example.com/v1/chat/completions?api_key=secret",
            "target_api_key": "super-secret",
            "target_body": {"apiKey": "super-secret", "temperature": 0},
        },
    )



def build_expert(name: str) -> ExpertVerdict:
    return ExpertVerdict(
        expert_name=name,
        evaluation_status="success",
        risk_score=0.2,
        confidence=0.8,
        critical=False,
        risk_tier="MINIMAL",
        summary="ok",
        findings=[],
        detail_payload=ExpertDetailPayload(evaluation_status="success"),
        evidence={},
    )



def test_audit_redacts_sensitive_fields(tmp_path: Path):
    configure_test_paths(tmp_path)
    audit = importlib.import_module("app.audit")
    audit = importlib.reload(audit)

    request = build_request()
    council = CouncilResult(
        decision="APPROVE",
        council_score=0.2,
        needs_human_review=False,
        rationale="baseline safe",
        consensus_summary="experts aligned on low risk",
        cross_expert_critique=["team perspectives were consistent"],
        recommended_actions=["keep current controls documented"],
        disagreement_index=0.0,
        triggered_by=[],
        key_evidence=[],
        ignored_signals=[],
        decision_rule_version="matrix-v1",
    )
    evaluation_id, report_path, archive_path = audit.persist_evaluation(
        request=request,
        experts=[build_expert("team1_policy_expert")],
        council=council,
        markdown_report="# Test report\n",
    )

    assert evaluation_id
    assert report_path.suffix == ".md"
    report = json.loads(archive_path.read_text(encoding="utf-8"))
    assert report["request"]["metadata"].get("target_api_key") is None
    assert report["request"]["metadata"]["target_endpoint"] == "https://example.com/v1/chat/completions"
    assert report["request"]["metadata"]["target_body"]["apiKey"] == "[REDACTED]"
    assert "metadata.target_api_key" in report["redaction_summary"]["redacted_fields"]
