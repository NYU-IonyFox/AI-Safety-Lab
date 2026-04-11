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
        f"- **Initial council decision:** {council.initial_decision or council.decision}",
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

    lines.extend(["## What happens next"])
    lines.extend([f"- {item}" for item in _governance_next_steps(council)])
    lines.append("")

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

    deliberation_summary = _deliberation_summary_lines(council)
    if deliberation_summary:
        lines.append("## Plain-language deliberation summary")
        lines.extend([f"- {item}" for item in deliberation_summary])
        lines.append("")

    if council.deliberation_enabled and council.deliberation_trace:
        lines.append("## Deliberation trail")
        for item in council.deliberation_trace:
            target_suffix = f" -> {item.target_expert}" if item.target_expert else ""
            delta_suffix = f" (risk delta {item.risk_delta:+.2f})" if item.risk_delta else ""
            lines.append(f"- **{item.phase.upper()}** `{item.author_expert}{target_suffix}`: {item.summary}{delta_suffix}")
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
        stakeholder_lines = _stakeholder_takeaway_lines(expert)
        if stakeholder_lines:
            lines.append("- **What this means:**")
            lines.extend([f"  - {item}" for item in stakeholder_lines])
        if expert.findings:
            lines.append("- **Technical findings:**")
            lines.extend([f"  - {finding}" for finding in expert.findings[:8]])
        expert_evidence = _expert_evidence_lines(expert)
        if expert_evidence:
            lines.append("- **Expert-specific evidence:**")
            lines.extend([f"  - {item}" for item in expert_evidence])
        lines.append("")

    lines.extend(
        [
            "## Council evidence trail",
            f"- **Initial decision:** {council.initial_decision or council.decision}",
            f"- **Initial rule triggered:** `{council.initial_decision_rule_triggered or council.decision_rule_triggered or 'unspecified'}`",
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


def _stakeholder_takeaway_lines(expert: ExpertVerdict) -> list[str]:
    if expert.expert_name == "team1_policy_expert":
        return [
            "This review checks whether the repository has clear access, oversight, and accountability controls.",
            "The public intake workflow is not paired with enough visible access-control and escalation controls.",
            "Because external AI services are involved, ownership, review, and retention expectations should be documented before sign-off.",
        ]
    if expert.expert_name == "team2_redteam_expert":
        return [
            "This review asks how a real attacker could misuse the repository in practice.",
            "The upload workflow creates a credible hostile-file and prompt-injection path before safeguards clearly stop abuse.",
            "That means the system can be operationally abused, not just theoretically criticized.",
        ]
    if expert.expert_name == "team3_risk_expert":
        return [
            "This review focuses on the deployed system boundary rather than only prompts or policy wording.",
            "The same workflow combines public uploads, local media processing, and external AI services in one chain.",
            "That architecture needs stronger isolation, authentication, and deployment hardening before production use.",
        ]
    return []


def _deliberation_summary_lines(council: CouncilResult) -> list[str]:
    if not council.deliberation_trace:
        return []

    critiques = [item for item in council.deliberation_trace if item.phase == "critique"]
    revisions = [item for item in council.deliberation_trace if item.phase == "revision"]
    lines = ["The three experts reviewed each other's blind spots before the final decision."]
    if any(item.author_expert == "team2_redteam_expert" for item in critiques):
        lines.append("The adversarial expert asked peers to account for hostile-file and prompt-injection risk.")
    if any(item.author_expert == "team3_risk_expert" for item in critiques):
        lines.append("The system expert asked peers to reflect deployment-boundary and hardening gaps.")
    if any(item.author_expert == "team1_policy_expert" for item in critiques):
        lines.append("The policy expert pushed the council to reflect access-control and governance obligations.")
    if revisions:
        revision_summary = ", ".join(
            f"{_expert_title(item.author_expert)} {item.risk_delta:+.2f}" for item in revisions[:3]
        )
        lines.append(f"After deliberation, the risk view changed for: {revision_summary}.")
    return lines[:4]


def _governance_next_steps(council: CouncilResult) -> list[str]:
    if council.decision == "REJECT":
        return [
            "Do not move this repository into production or open pilot deployment yet.",
            "Assign engineering, security, and governance owners to close the listed gaps and capture the evidence of remediation.",
            "Rerun the evaluation after fixes and attach the updated report to the deployment or change-control record.",
        ]
    if council.decision == "REVIEW":
        return [
            "Pause deployment until a human reviewer signs off the listed mitigations.",
            "Use the expert findings and recommended actions to decide whether the case can move to APPROVE or must be sent back for remediation.",
            "Record the human decision together with this report so the governance trail stays auditable.",
        ]
    return [
        "This repository can move forward under normal change control rather than emergency escalation.",
        "Keep the current evidence trail, monitoring, and controls attached to the deployment record.",
        "If the repository scope changes materially, rerun the evaluation before the next production release.",
    ]


def _expert_evidence_lines(expert: ExpertVerdict) -> list[str]:
    evidence = expert.evidence or {}

    if expert.expert_name == "team1_policy_expert":
        lines = []
        controls = [str(item) for item in evidence.get("policy_scope_controls", []) if str(item).strip()]
        if controls:
            normalized = [item.rstrip(".") for item in controls[:3]]
            lines.append(f"Governance controls observed: {', '.join(normalized)}.")
        policy_evidence = evidence.get("policy_scope_evidence", [])
        if isinstance(policy_evidence, list):
            for item in policy_evidence[:2]:
                if isinstance(item, dict):
                    lines.append(f"{item.get('path', 'unknown')}: {item.get('signal', 'Policy evidence')}.")
        return lines[:3]

    if expert.expert_name == "team2_redteam_expert":
        lines = []
        taxonomy = evidence.get("taxonomy", {})
        if isinstance(taxonomy, dict):
            owasp = [str(item) for item in taxonomy.get("owasp_categories", []) if str(item).strip()]
            mitre = [str(item) for item in taxonomy.get("mitre_tactics", []) if str(item).strip()]
            if owasp:
                lines.append(f"OWASP categories exercised: {', '.join(owasp[:3])}.")
            if mitre:
                lines.append(f"MITRE-style tactics exercised: {', '.join(mitre[:3])}.")
        redteam_surface = evidence.get("redteam_surface", {})
        if isinstance(redteam_surface, dict):
            signals = [str(item) for item in redteam_surface.get("surface_signals", []) if str(item).strip()]
            if signals:
                lines.append(f"Threat-surface signals: {', '.join(signals[:3])}.")
        return lines[:3]

    if expert.expert_name == "team3_risk_expert":
        lines = []
        scope_evidence = evidence.get("system_scope_evidence", [])
        if isinstance(scope_evidence, list):
            for item in scope_evidence[:2]:
                if isinstance(item, dict):
                    lines.append(f"{item.get('path', 'unknown')}: {item.get('signal', 'System evidence')}.")
        rule_baseline = evidence.get("rule_baseline", {})
        if isinstance(rule_baseline, dict):
            risk_tier = str(rule_baseline.get("risk_tier", "")).strip()
            if risk_tier:
                lines.append(f"Baseline system tier before protocol synthesis: {risk_tier}.")
        return lines[:3]

    return []
