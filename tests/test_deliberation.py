from app.deliberation import run_deliberation
from app.schemas import (
    AgentContext,
    EvaluationRequest,
    ExpertDetailPayload,
    ExpertVerdict,
    RepositoryEvidence,
    RepositorySummary,
)


def _make_verdict(name: str, risk: float, summary: str, findings: list[str]) -> ExpertVerdict:
    return ExpertVerdict(
        expert_name=name,
        evaluation_status="success",
        risk_score=risk,
        confidence=0.7,
        critical=False,
        risk_tier="HIGH" if risk >= 0.65 else "LIMITED",
        summary=summary,
        findings=findings,
        detail_payload=ExpertDetailPayload(),
        evidence={},
    )


def test_deliberation_generates_critiques_and_revision_for_missing_repo_risk() -> None:
    request = EvaluationRequest(
        context=AgentContext(agent_name="VeriMedia"),
        repository_summary=RepositorySummary(
            target_name="VeriMedia",
            source_type="github_url",
            resolved_path="/tmp/verimedia",
            description="",
            framework="Flask",
            entrypoints=["/upload"],
            llm_backends=["GPT-4o"],
            media_modalities=["text", "audio"],
            upload_surfaces=["request.files upload handling"],
            auth_signals=["no_explicit_auth"],
            secret_signals=["default_secret_key_fallback"],
            dependencies=[],
            notable_files=["app.py"],
            risk_notes=[],
            detected_signals=[],
            evidence_items=[
                RepositoryEvidence(path="app.py:1", signal="Upload route detected", why_it_matters=""),
                RepositoryEvidence(path="app.py:2", signal="No auth", why_it_matters=""),
            ],
            file_count=1,
            summary="VeriMedia is a Flask repository with uploads and external AI usage.",
        ),
    )
    verdicts = [
        _make_verdict(
            "team3_risk_expert",
            0.78,
            "System-risk review found elevated architecture exposure.",
            ["Upload pipeline is connected to external AI services."],
        ),
        _make_verdict(
            "team2_redteam_expert",
            0.50,
            "Adversarial review found some misuse risk.",
            ["Potential misuse indicators were present."],
        ),
        _make_verdict(
            "team1_policy_expert",
            0.76,
            "Governance review found policy gaps.",
            ["Access control is not clearly documented."],
        ),
    ]

    result = run_deliberation(request, verdicts)

    assert any(item.phase == "critique" for item in result.trace)
    assert any(item.phase == "revision" for item in result.trace)
    revised_team2 = next(item for item in result.revised_verdicts if item.expert_name == "team2_redteam_expert")
    assert revised_team2.risk_score > 0.50
    assert any("Deliberation revision" in finding for finding in revised_team2.findings)


def test_deliberation_uses_differentiated_evidence_refs_by_expert_lens() -> None:
    request = EvaluationRequest(
        context=AgentContext(agent_name="VeriMedia"),
        repository_summary=RepositorySummary(
            target_name="VeriMedia",
            source_type="github_url",
            resolved_path="/tmp/verimedia",
            description="",
            framework="Flask",
            entrypoints=["/upload"],
            llm_backends=["OpenAI API", "GPT-4o", "Whisper API"],
            media_modalities=["text", "audio", "video"],
            upload_surfaces=["request.files upload handling"],
            auth_signals=["no_explicit_auth"],
            secret_signals=["default_secret_key_fallback"],
            dependencies=[],
            notable_files=["app.py", "README.md"],
            risk_notes=[],
            detected_signals=[],
            evidence_items=[
                RepositoryEvidence(path="app.py:301", signal="Upload route detected", why_it_matters="Public upload surface."),
                RepositoryEvidence(path="app.py:308", signal="Uploaded files are read from HTTP requests", why_it_matters="Hostile file risk."),
                RepositoryEvidence(path="app.py:296", signal="No explicit authentication controls detected in analyzed files", why_it_matters="Abuse is easier."),
                RepositoryEvidence(path="README.md:110", signal="GPT-4o model usage detected", why_it_matters="External model boundary."),
                RepositoryEvidence(path="app.py:26", signal="Development secret-key fallback detected", why_it_matters="Deployment hardening weakness."),
                RepositoryEvidence(path="README.md:8", signal="Speech or media transcription detected", why_it_matters="Audio/video handling broadens exposure."),
            ],
            file_count=2,
            summary="VeriMedia is a Flask repository with uploads and external AI usage.",
        ),
    )
    verdicts = [
        _make_verdict("team3_risk_expert", 0.78, "System review found elevated exposure.", ["Pipeline review needed."]),
        _make_verdict("team2_redteam_expert", 0.50, "Adversarial review found some misuse risk.", ["Potential misuse indicators were present."]),
        _make_verdict("team1_policy_expert", 0.76, "Governance review found policy gaps.", ["Controls should be documented."]),
    ]

    trace = run_deliberation(request, verdicts).trace
    critiques = [item for item in trace if item.phase == "critique"]

    team1_refs = next(item.evidence_refs for item in critiques if item.author_expert == "team1_policy_expert")
    team2_refs = next(item.evidence_refs for item in critiques if item.author_expert == "team2_redteam_expert")
    team3_refs = next(item.evidence_refs for item in critiques if item.author_expert == "team3_risk_expert")

    assert "app.py:296" in team1_refs
    assert "app.py:308" in team2_refs
    assert "app.py:26" in team3_refs or "README.md:8" in team3_refs
    assert team1_refs != team2_refs
    assert team2_refs != team3_refs
