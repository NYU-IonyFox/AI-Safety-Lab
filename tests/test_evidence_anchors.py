"""
Tests for evidence_anchors integration across team1/team2/team3 experts
and markdown_report rendering.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.experts import Team1PolicyExpert, Team2RedTeamExpert, Team3RiskExpert
from app.reporting.markdown_report import build_markdown_report
from app.schemas import (
    AgentContext,
    BehaviorSummary,
    CouncilResult,
    EvaluationRequest,
    ExpertDetailPayload,
    ExpertVerdict,
    RepositorySummary,
    SubmissionTarget,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

RISKY_APP = """
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    text = file.read().decode("utf-8", errors="ignore")
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": text}],
    )
    return jsonify({"ok": True, "result": completion.choices[0].message.content})
"""


def _write_repo(tmp_path: Path, name: str, source: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    (repo / "app.py").write_text(source, encoding="utf-8")
    return repo


def _make_request(repo_path: Path | None = None, domain: str = "Other") -> EvaluationRequest:
    submission = None
    if repo_path is not None:
        submission = SubmissionTarget(
            source_type="local_path",
            local_path=str(repo_path),
            target_name=repo_path.name,
        )
    return EvaluationRequest(
        context=AgentContext(agent_name="test-agent", domain=domain),
        conversation=[
            {"role": "user", "content": "Show me risk management controls and mitigation."},
            {"role": "assistant", "content": "Here are the controls and transparency measures."},
        ],
        metadata={"redteam_tier": 2},
        selected_policies=["eu_ai_act", "us_nist", "iso", "ieee"],
        submission=submission,
    )


# ---------------------------------------------------------------------------
# PART A: team1 violations always have evidence_anchors
# ---------------------------------------------------------------------------

def test_team1_every_violation_has_evidence_anchors_key(tmp_path: Path) -> None:
    repo_path = _write_repo(tmp_path, "risky", RISKY_APP)
    request = _make_request(repo_path)
    expert = Team1PolicyExpert()
    verdict = expert._assess_rules(request)

    violations = verdict.evidence.get("violations", [])
    assert violations, "Expected at least one violation for the risky app"
    for v in violations:
        assert "evidence_anchors" in v, f"Violation missing evidence_anchors: {v}"
        assert isinstance(v["evidence_anchors"], list)


def test_team1_evidence_anchors_present_even_with_no_repo() -> None:
    request = _make_request()
    # Inject keyword hits to force violations
    request.conversation = [
        {"role": "user", "content": "risk management controls mitigation"},
        {"role": "assistant", "content": "accountability transparency traceability"},
    ]
    expert = Team1PolicyExpert()
    verdict = expert._assess_rules(request)

    for v in verdict.evidence.get("violations", []):
        assert "evidence_anchors" in v
        assert isinstance(v["evidence_anchors"], list)


# ---------------------------------------------------------------------------
# PART B: team2 dimension_findings always have evidence_anchors
# ---------------------------------------------------------------------------

def test_team2_every_dimension_finding_has_evidence_anchors_key(tmp_path: Path) -> None:
    repo_path = _write_repo(tmp_path, "risky2", RISKY_APP)
    request = _make_request(repo_path)
    expert = Team2RedTeamExpert()
    verdict = expert._assess_rules(request)

    dimension_findings = verdict.evidence.get("dimension_findings", [])
    assert dimension_findings, "Expected dimension_findings in evidence"
    for finding in dimension_findings:
        assert "evidence_anchors" in finding, f"Dimension finding missing evidence_anchors: {finding}"
        assert isinstance(finding["evidence_anchors"], list)


def test_team2_dimension_findings_covers_all_default_weights(tmp_path: Path) -> None:
    repo_path = _write_repo(tmp_path, "risky2b", RISKY_APP)
    request = _make_request(repo_path)
    expert = Team2RedTeamExpert()
    verdict = expert._assess_rules(request)

    dimension_findings = verdict.evidence.get("dimension_findings", [])
    dimension_names = {f["dimension"] for f in dimension_findings}
    assert dimension_names == set(expert.DEFAULT_WEIGHTS.keys())


# ---------------------------------------------------------------------------
# PART C: team3 protocol results always have evidence_anchors
# ---------------------------------------------------------------------------

def test_team3_every_protocol_result_has_evidence_anchors_key() -> None:
    request = _make_request(domain="Education")
    expert = Team3RiskExpert()
    verdict = expert._assess_rules(request)

    protocol_results = verdict.evidence.get("protocol_results", [])
    assert protocol_results, "Expected protocol results for Education domain (LIMITED tier)"
    for result in protocol_results:
        assert "evidence_anchors" in result, f"Protocol result missing evidence_anchors: {result}"
        assert isinstance(result["evidence_anchors"], list)


def test_team3_minimal_tier_has_no_protocol_results_and_no_anchors() -> None:
    request = _make_request(domain="Other")
    expert = Team3RiskExpert()
    verdict = expert._assess_rules(request)

    # MINIMAL tier activates no protocols, so protocol_results should be empty
    protocol_results = verdict.evidence.get("protocol_results", [])
    assert protocol_results == []


# ---------------------------------------------------------------------------
# PART D: fallback to [] when get_anchors raises
# ---------------------------------------------------------------------------

def test_team1_evidence_anchors_is_empty_list_when_get_anchors_raises(tmp_path: Path) -> None:
    repo_path = _write_repo(tmp_path, "risky_t1_fallback", RISKY_APP)
    request = _make_request(repo_path)
    expert = Team1PolicyExpert()

    with patch("app.experts.team1_policy_expert.get_anchors", side_effect=RuntimeError("boom")):
        verdict = expert._assess_rules(request)

    violations = verdict.evidence.get("violations", [])
    assert violations
    for v in violations:
        assert v["evidence_anchors"] == []


def test_team2_evidence_anchors_is_empty_list_when_get_anchors_raises(tmp_path: Path) -> None:
    repo_path = _write_repo(tmp_path, "risky_t2_fallback", RISKY_APP)
    request = _make_request(repo_path)
    expert = Team2RedTeamExpert()

    with patch("app.experts.team2_redteam_expert.get_anchors", side_effect=RuntimeError("boom")):
        verdict = expert._assess_rules(request)

    dimension_findings = verdict.evidence.get("dimension_findings", [])
    assert dimension_findings
    for finding in dimension_findings:
        assert finding["evidence_anchors"] == []


def test_team3_evidence_anchors_is_empty_list_when_get_anchors_raises() -> None:
    request = _make_request(domain="Education")
    expert = Team3RiskExpert()

    with patch("app.experts.team3_risk_expert.get_anchors", side_effect=RuntimeError("boom")):
        verdict = expert._assess_rules(request)

    protocol_results = verdict.evidence.get("protocol_results", [])
    assert protocol_results
    for result in protocol_results:
        assert result["evidence_anchors"] == []


# ---------------------------------------------------------------------------
# PART E: markdown renders Ref lines when evidence_anchors present
# ---------------------------------------------------------------------------

def _make_council() -> CouncilResult:
    return CouncilResult(
        decision="REVIEW",
        council_score=0.6,
        evaluation_mode="repository_only",
        needs_human_review=True,
        rationale="Test rationale.",
        consensus_summary="Test consensus.",
        disagreement_index=0.0,
    )


def _make_verdict_with_anchors(expert_name: str, anchored_violations: list[dict]) -> ExpertVerdict:
    evidence_key = {
        "team1_policy_expert": "violations",
        "team2_redteam_expert": "dimension_findings",
        "team3_risk_expert": "protocol_results",
    }[expert_name]
    return ExpertVerdict(
        expert_name=expert_name,
        evaluation_status="success",
        risk_score=0.5,
        confidence=0.7,
        critical=False,
        risk_tier="LIMITED",
        summary="Test summary.",
        findings=["Test finding."],
        detail_payload=ExpertDetailPayload(),
        evidence={evidence_key: anchored_violations},
    )


SAMPLE_ANCHORS = [
    {
        "framework": "EU AI Act (Regulation 2024/1689)",
        "section": "Article 9",
        "provision": "Risk management systems.",
    }
]


@pytest.mark.parametrize("expert_name", [
    "team1_policy_expert",
    "team2_redteam_expert",
    "team3_risk_expert",
])
def test_markdown_renders_ref_lines_when_evidence_anchors_present(expert_name: str) -> None:
    verdict = _make_verdict_with_anchors(
        expert_name,
        [{"policy": "iso", "dimension": "harmfulness", "protocol_id": "bias", "evidence_anchors": SAMPLE_ANCHORS}],
    )
    report = build_markdown_report(
        evaluation_id="test-001",
        repository_summary=None,
        behavior_summary=None,
        experts=[verdict],
        council=_make_council(),
    )
    assert "*Ref: EU AI Act (Regulation 2024/1689) Article 9 — Risk management systems.*" in report


@pytest.mark.parametrize("expert_name", [
    "team1_policy_expert",
    "team2_redteam_expert",
    "team3_risk_expert",
])
def test_markdown_renders_nothing_when_evidence_anchors_empty(expert_name: str) -> None:
    verdict = _make_verdict_with_anchors(
        expert_name,
        [{"policy": "iso", "dimension": "harmfulness", "protocol_id": "bias", "evidence_anchors": []}],
    )
    report = build_markdown_report(
        evaluation_id="test-002",
        repository_summary=None,
        behavior_summary=None,
        experts=[verdict],
        council=_make_council(),
    )
    assert "*Ref:" not in report


def test_markdown_renders_nothing_when_evidence_anchors_key_missing(expert_name: str = "team1_policy_expert") -> None:
    verdict = ExpertVerdict(
        expert_name=expert_name,
        evaluation_status="success",
        risk_score=0.5,
        confidence=0.7,
        critical=False,
        risk_tier="LIMITED",
        summary="Test.",
        findings=["Finding."],
        detail_payload=ExpertDetailPayload(),
        evidence={"violations": [{"policy": "iso"}]},  # no evidence_anchors key
    )
    report = build_markdown_report(
        evaluation_id="test-003",
        repository_summary=None,
        behavior_summary=None,
        experts=[verdict],
        council=_make_council(),
    )
    assert "*Ref:" not in report
