from __future__ import annotations

from app.schemas import CouncilResult, ExpertVerdict, RepositorySummary


EXPERT_TITLES = {
    "team1_policy_expert": "Policy & Compliance",
    "team2_redteam_expert": "Adversarial Misuse",
    "team3_risk_expert": "System & Deployment",
}


def build_markdown_report(
    *,
    evaluation_id: str,
    repository_summary: RepositorySummary | None,
    experts: list[ExpertVerdict],
    council: CouncilResult,
) -> str:
    repo = repository_summary
    lines = [
        "# AI Safety Lab Stakeholder Evaluation Report",
        "",
        "## Verdict at a glance",
        f"- **Final decision:** {council.decision}",
        f"- **Council score:** {council.council_score:.2f}",
        f"- **Human review required:** {'Yes' if council.needs_human_review else 'No'}",
        f"- **Arbitration rule triggered:** `{council.decision_rule_triggered or 'unspecified'}`",
        f"- **Evaluation ID:** `{evaluation_id}`",
        "",
        "## Executive takeaway",
        council.rationale,
        "",
        council.consensus_summary,
        "",
    ]

    if repo is not None:
        lines.extend(
            [
                "## What was reviewed",
                f"- **Target:** {repo.target_name}",
                f"- **Submission source:** `{repo.source_type}`",
                f"- **Detected framework:** {repo.framework}",
                f"- **AI backends:** {', '.join(repo.llm_backends) if repo.llm_backends else 'None clearly detected'}",
                f"- **Media handled:** {', '.join(repo.media_modalities) if repo.media_modalities else 'Not clearly detected'}",
                f"- **Upload surface:** {', '.join(repo.upload_surfaces) if repo.upload_surfaces else 'None clearly detected'}",
                f"- **Auth signals:** {', '.join(repo.auth_signals) if repo.auth_signals else 'None clearly detected'}",
                "",
                "## Repository-level interpretation",
                repo.summary,
                "",
            ]
        )
        if repo.detected_signals:
            lines.append("## Detected repository signals")
            lines.extend([f"- {item}" for item in repo.detected_signals])
            lines.append("")
        if repo.evidence_items:
            lines.append("## Evidence from repository")
            lines.extend(
                [
                    f"- **{item.path}**: {item.signal}. {item.why_it_matters}"
                    for item in repo.evidence_items
                ]
            )
            lines.append("")
        if repo.risk_notes:
            lines.append("## Why the repository matters from a safety perspective")
            lines.extend([f"- {item}" for item in repo.risk_notes])
            lines.append("")

    if council.cross_expert_critique:
        lines.append("## Cross-expert critique")
        lines.extend([f"- {item}" for item in council.cross_expert_critique])
        lines.append("")

    lines.append("## Expert views")
    for expert in experts:
        lines.extend(
            [
                f"### {_expert_title(expert.expert_name)}",
                f"- **Status:** `{expert.evaluation_status}`",
                f"- **Risk tier:** {expert.risk_tier}",
                f"- **Risk score:** {expert.risk_score:.2f}",
                f"- **Confidence:** {expert.confidence:.2f}",
                f"- **Bottom line:** {expert.summary}",
            ]
        )
        if expert.findings:
            lines.append("- **Key findings:**")
            lines.extend([f"  - {finding}" for finding in expert.findings[:8]])
        lines.append("")

    lines.extend(
        [
            "## Council evidence trail",
            f"- **Decision rule triggered:** `{council.decision_rule_triggered or 'unspecified'}`",
            f"- **Triggered by:** {', '.join(council.triggered_by) if council.triggered_by else 'None'}",
            f"- **Disagreement index:** {council.disagreement_index:.2f}",
        ]
    )
    if council.key_evidence:
        lines.append("- **Key evidence used in the final decision:**")
        lines.extend([f"  - {item}" for item in council.key_evidence])
    if council.ignored_signals:
        lines.append("- **Signals noted but not decisive on their own:**")
        lines.extend([f"  - {item}" for item in council.ignored_signals])

    lines.extend(["", "## Recommended actions before sign-off"])
    if council.recommended_actions:
        lines.extend([f"- {item}" for item in council.recommended_actions])
    else:
        lines.extend(
            [
                "- Review upload and media-processing boundaries before production deployment.",
                "- Add or verify authentication and access control around analysis endpoints.",
                "- Validate external LLM/transcription calls, secrets handling, and prompt-injection exposure.",
            ]
        )

    return "\n".join(lines).strip() + "\n"



def _expert_title(expert_name: str) -> str:
    return EXPERT_TITLES.get(expert_name, expert_name)
