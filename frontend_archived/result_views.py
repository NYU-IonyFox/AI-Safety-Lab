from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


def _escape(text: object) -> str:
    value = "" if text is None else str(text)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

try:
    import ui_styles
except ImportError:  # pragma: no cover - fallback keeps the module usable before the helper lands.
    class _FallbackUIStyles:
        @staticmethod
        def render_metric_card(label: str, value: str, tone_class: str, copy: str) -> None:
            st.markdown(
                f"""
                <div class="metric-card {tone_class}">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                    <div class="metric-copy">{copy}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        @staticmethod
        def tone_for_decision(decision: str) -> str:
            value = str(decision).upper()
            if value == "REJECT":
                return "tone-red"
            if value == "REVIEW":
                return "tone-yellow"
            return "tone-green"

        @staticmethod
        def tone_for_risk(risk_level: str) -> str:
            value = str(risk_level).upper()
            if value in {"HIGH", "UNACCEPTABLE", "TIER_4", "TIER_3"}:
                return "tone-red"
            if value in {"MEDIUM", "LIMITED", "REVIEW_REQUIRED", "TIER_2"}:
                return "tone-yellow"
            return "tone-green"

        @staticmethod
        def risk_class(risk_level: str) -> str:
            value = str(risk_level).lower()
            if value in {"high", "unacceptable", "tier_4", "tier_3"}:
                return "risk-high"
            if value in {"medium", "limited", "review_required", "tier_2"}:
                return "risk-medium"
            return "risk-low"

    ui_styles = _FallbackUIStyles()


APP_TITLE = "AI Safety Lab"
APP_SUBTITLE = "Stakeholder-ready council output with summary, evidence, expert modules, and traceability."

RISK_ORDER = {
    "UNKNOWN": 0,
    "LOW": 1,
    "TIER_1": 1,
    "LIMITED": 2,
    "REVIEW_REQUIRED": 2,
    "MEDIUM": 3,
    "TIER_2": 3,
    "HIGH": 4,
    "TIER_3": 4,
    "UNACCEPTABLE": 5,
    "TIER_4": 5,
}


def _inject_styles() -> None:
    return None


def _display_text(value: object, default: str = "Not available") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _display_lines(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _render_html_card(
    class_name: str,
    title: str,
    copy: str | None = None,
    body_html: str = "",
) -> None:
    parts = [f'<div class="{class_name}">', f'<h3 class="card-title">{_escape(title)}</h3>']
    if copy:
        parts.append(f'<p class="body-copy">{_escape(copy)}</p>')
    if body_html:
        parts.append(body_html)
    parts.append("</div>")
    st.markdown("\n".join(parts), unsafe_allow_html=True)


def _render_html_list(items: list[str], *, limit: int | None = None) -> str:
    values = [item for item in items if str(item).strip()]
    if limit is not None:
        values = values[:limit]
    if not values:
        return ""
    return "<ul class=\"card-list\">" + "".join(f"<li>{_escape(item)}</li>" for item in values) + "</ul>"


def _render_kv_grid(items: list[tuple[str, str]]) -> str:
    body = ['<div class="kv-grid">']
    for label, value in items:
        body.append(
            "<div class=\"kv-item\">"
            f"<div class=\"kv-label\">{_escape(label)}</div>"
            f"<div class=\"kv-value\">{_escape(value)}</div>"
            "</div>"
        )
    body.append("</div>")
    return "".join(body)


def _display_workflow(result: dict) -> str:
    repo = result.get("repository_summary") or {}
    expert_input = result.get("expert_input") or {}
    source_conversation = expert_input.get("source_conversation", []) if isinstance(expert_input, dict) else []
    if repo and source_conversation:
        return "Hybrid"
    if repo:
        return "Repository-only"
    if source_conversation:
        return "Behavior-only"
    behavior = result.get("behavior_summary") or {}
    mode = str(behavior.get("evaluation_mode", "")).replace("_", "-").title()
    return mode if mode and mode != "None" else "Behavior-only"


def _risk_rank(value: object) -> int:
    return RISK_ORDER.get(str(value).upper(), 0)


def _highest_risk_tier(experts: list[dict], behavior_summary: dict | None) -> str:
    candidates = [str(expert.get("risk_tier", "UNKNOWN")) for expert in experts if isinstance(expert, dict)]
    if behavior_summary and behavior_summary.get("uncertainty_flag"):
        candidates.append("MEDIUM")
    if not candidates:
        return "UNKNOWN"
    return max(candidates, key=_risk_rank)


def _expert_title(expert_name: str) -> str:
    mapping = {
        "team1_policy_expert": "Governance, Compliance & Societal Risk",
        "team2_redteam_expert": "Data, Content & Behavioral Safety",
        "team3_risk_expert": "Security & Adversarial Robustness",
    }
    return mapping.get(expert_name, expert_name or "Expert")


def _trigger_label(value: str) -> str:
    mapping = {
        "team1_policy_expert": "Governance, Compliance & Societal Risk",
        "team2_redteam_expert": "Data, Content & Behavioral Safety",
        "team3_risk_expert": "Security & Adversarial Robustness",
        "disagreement": "Expert disagreement",
    }
    return mapping.get(value, value.replace("_", " "))


def _decision_rule_label(value: str) -> str:
    if not value:
        return "Unspecified"
    return value.replace("_", " ")


def _workflow_scope_summary(result: dict) -> list[str]:
    repo = result.get("repository_summary") or {}
    behavior = result.get("behavior_summary") or {}
    expert_input = result.get("expert_input") or {}
    source_turns = len(expert_input.get("source_conversation", [])) if isinstance(expert_input, dict) else 0

    lines: list[str] = []
    if repo:
        lines.append(f"Repository target: {repo.get('target_name', 'Unknown')}.")
        lines.append(f"Framework: {repo.get('framework', 'Unknown')}.")
        lines.append(f"Source type: {repo.get('source_type', 'manual')}.")
        if repo.get("summary"):
            lines.append(str(repo.get("summary")))
    else:
        lines.append("No repository summary was returned for this evaluation.")

    if behavior:
        lines.append(f"Evaluation mode: {behavior.get('evaluation_mode', 'repository_only')}.")
        lines.append(f"Transcript present: {'Yes' if behavior.get('transcript_present') else 'No'}.")
        lines.append(f"Primary language: {behavior.get('primary_language', 'unknown')}.")
        lines.append(f"Translation confidence: {float(behavior.get('translation_confidence', 1.0)):.2f}.")
        if behavior.get("summary"):
            lines.append(str(behavior.get("summary")))
        if behavior.get("uncertainty_flag"):
            lines.append("Behavior review raised an uncertainty flag.")
    else:
        lines.append("No behavior summary was returned for this evaluation.")

    if source_turns:
        lines.append(f"Conversation input supplied {source_turns} turn(s).")
    return lines


def _decision_badge_class(decision: str) -> str:
    value = str(decision).strip().upper()
    if value == "REJECT":
        return "badge-reject"
    if value == "REVIEW":
        return "badge-review"
    if value == "APPROVE":
        return "badge-approve"
    return "badge-info"


def _render_chips(result: dict) -> None:
    evaluation_id = _display_text(result.get("evaluation_id"), "Pending")
    workflow = _display_workflow(result)
    council = result.get("council_result") or {}
    decision = _display_text(result.get("decision"), "REVIEW")
    review_chip = "Human review required" if council.get("needs_human_review") else "Auto-approved path"
    archive_path = _display_text(result.get("archive_path"), "")
    report_path = _display_text(result.get("report_path"), "")
    badge_class = _decision_badge_class(decision)

    artifact_pills = ""
    if archive_path:
        artifact_pills += '<span class="pill pill-neutral">&#128190;&nbsp; Archive saved</span>'
    if report_path:
        artifact_pills += '<span class="pill pill-green">&#128196;&nbsp; Report saved</span>'

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-eyebrow">Stakeholder Dashboard</div>
            <div class="hero-title">&#128202;&nbsp; Evaluation Result</div>
            <div class="hero-copy">{APP_SUBTITLE}</div>
            <div class="pill-row">
                <span class="badge {badge_class}">{_escape(decision)}</span>
                <span class="pill pill-neutral">&#9881;&nbsp; {_escape(workflow)}</span>
                <span class="pill pill-neutral" style="font-family:monospace;font-size:0.72rem;">{_escape(evaluation_id[:16])}…</span>
                {'<span class="pill pill-blue">&#128100;&nbsp; ' + review_chip + '</span>' if council.get("needs_human_review") else '<span class="pill pill-green">&#10003;&nbsp; ' + review_chip + '</span>'}
                {artifact_pills}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_action_bar(result: dict) -> None:
    evaluation_id = _display_text(result.get("evaluation_id"), "Pending")
    decision = _display_text(result.get("decision"), "REVIEW")
    council = result.get("council_result") or {}
    mode = _display_workflow(result)

    left, right = st.columns([0.24, 0.76])
    with left:
        if st.button("Back to Inputs", use_container_width=True):
            st.session_state.current_page = "input"
            st.rerun()
    with right:
        note = [
            f"Decision: {decision}",
            f"Mode: {mode}",
            f"Evaluation ID: {evaluation_id}",
        ]
        if council.get("needs_human_review"):
            note.append("Status: human review required")
        st.markdown(
            f"""
            <div class="section-card card-flush">
                <div class="action-note">
                {' &nbsp;•&nbsp; '.join(note)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_metric_row(result: dict) -> None:
    council = result.get("council_result") or {}
    experts = result.get("experts") or []
    behavior = result.get("behavior_summary") or {}
    decision = _display_text(result.get("decision"), "REVIEW")
    highest_risk = _highest_risk_tier(experts if isinstance(experts, list) else [], behavior if isinstance(behavior, dict) else None)
    disagreement_index = float(council.get("disagreement_index", 0.0))
    score = float(council.get("council_score", 0.0))

    tone = ui_styles.tone_for_decision(decision)
    copy = _decision_copy(decision)
    tone_risk = ui_styles.tone_for_risk(highest_risk)
    risk_copy = _risk_copy(highest_risk)
    score_tone = "tone-blue"
    score_copy = "Council synthesis score produced by the arbitration layer."

    col1, col2, col3 = st.columns(3)
    with col1:
        ui_styles.render_metric_card("Final Decision", decision, tone, copy)
    with col2:
        ui_styles.render_metric_card("Highest Risk Tier", highest_risk, tone_risk, risk_copy)
    with col3:
        ui_styles.render_metric_card("Council Score", f"{score:.2f}", score_tone, score_copy)

    st.markdown(
        f"""
        <div class="section-card">
            <div class="kv-grid">
                <div class="kv-item">
                    <div class="kv-label">Disagreement index</div>
                    <div class="kv-value">{disagreement_index:.2f}</div>
                </div>
                <div class="kv-item">
                    <div class="kv-label">Human review</div>
                    <div class="kv-value">{'Yes' if council.get('needs_human_review') else 'No'}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_overview(result: dict) -> None:
    repo = result.get("repository_summary") or {}
    behavior = result.get("behavior_summary") or {}
    submission = result.get("submission") or {}
    expert_input = result.get("expert_input") or {}
    source_turns = len(expert_input.get("source_conversation", [])) if isinstance(expert_input, dict) else 0
    workflow = _display_workflow(result)

    left, right = st.columns([1.1, 0.9])
    with left:
        lines = [f"<div class=\"card-copy\"><strong>Workflow:</strong> {_escape(workflow)}</div>"]
        if repo:
            lines.append(f"<div class=\"card-copy\"><strong>Target:</strong> {_escape(_display_text(repo.get('target_name'), 'Unknown'))}</div>")
            lines.append(f"<div class=\"card-copy\"><strong>Framework:</strong> {_escape(_display_text(repo.get('framework'), 'Unknown'))}</div>")
            lines.append(
                f"<div class=\"card-copy\"><strong>Source type:</strong> {_escape(_display_text(repo.get('source_type', submission.get('source_type')), 'manual'))}</div>"
            )
            lines.append(
                f"<div class=\"card-copy\"><strong>Repository summary:</strong> {_escape(_display_text(repo.get('summary'), 'No summary available.'))}</div>"
            )
        else:
            lines.append(f"<div class=\"card-copy\"><strong>Target:</strong> {_escape(_display_text(submission.get('target_name'), 'Transcript review'))}</div>")
            lines.append("<div class=\"card-copy\"><strong>Framework:</strong> Behavior-only transcript review</div>")
            lines.append("<div class=\"card-copy\"><strong>Source type:</strong> manual / transcript</div>")
            lines.append("<div class=\"card-copy\"><strong>Repository summary:</strong> No repository artifact was returned for this evaluation.</div>")
        _render_html_card(
            "section-card",
            "Submission summary",
            "High-level context for the submitted repository, transcript, or hybrid review.",
            "".join(lines),
        )

    with right:
        body_parts: list[str] = []
        if repo:
            body_parts.append(f"<div class=\"card-copy\"><strong>Detected signals</strong></div>{_render_html_list(_display_lines(repo.get('detected_signals')), limit=4)}")
            body_parts.append(f"<div class=\"card-copy\"><strong>Risk notes</strong></div>{_render_html_list(_display_lines(repo.get('risk_notes')), limit=4)}")
            body_parts.append(f"<div class=\"card-copy\"><strong>Notable files</strong></div>{_render_html_list(_display_lines(repo.get('notable_files')), limit=4)}")
        else:
            body_parts.append(
                "<div class=\"card-copy\"><strong>Transcript coverage</strong></div>"
                + _render_html_list(
                    [
                        f"{source_turns} conversation turn(s) supplied in the payload.",
                        "The council reviews behavior evidence directly from the transcript.",
                    ]
                )
            )
        if behavior:
            body_parts.append(
                "<div class=\"card-copy\"><strong>Behavior summary</strong></div>"
                + _render_html_list(
                    [
                        f"Detected languages: {', '.join(_display_lines(behavior.get('detected_languages'))) or 'None explicitly tagged'}.",
                        f"Primary language: {_display_text(behavior.get('primary_language'), 'unknown')}.",
                        f"Translation confidence: {float(behavior.get('translation_confidence', 1.0)):.2f}.",
                        f"Uncertainty flag: {'Yes' if behavior.get('uncertainty_flag') else 'No'}.",
                    ]
                )
            )
        _render_html_card(
            "section-card",
            "Evidence snapshot",
            "Condensed signals and behavior markers surfaced before the detailed drill-down.",
            "".join(body_parts),
        )


def _render_evidence_sections(result: dict) -> None:
    repo = result.get("repository_summary") or {}
    behavior = result.get("behavior_summary") or {}
    expert_input = result.get("expert_input") or {}
    source_turns = expert_input.get("source_conversation", []) if isinstance(expert_input, dict) else []

    columns = st.columns(2)
    with columns[0]:
        body_parts: list[str] = []
        evidence_items = repo.get("evidence_items", []) if isinstance(repo, dict) else []
        if evidence_items:
            body_parts.append('<ul class="card-list">')
            for item in evidence_items[:4]:
                path = _escape(_display_text(item.get("path"), "unknown"))
                signal = _escape(_display_text(item.get("signal"), "Signal"))
                why = _escape(_display_text(item.get("why_it_matters"), ""))
                body_parts.append(f"<li><code>{path}</code>: <strong>{signal}</strong>. {why}</li>")
            body_parts.append("</ul>")
        else:
            body_parts.append("<div class=\"card-copy\">No repository evidence items were returned for this run.</div>")
        body_parts.append(f"<div class=\"card-copy\"><strong>LLM backends</strong></div>{_render_html_list(_display_lines(repo.get('llm_backends')), limit=4)}")
        body_parts.append(f"<div class=\"card-copy\"><strong>Upload surfaces</strong></div>{_render_html_list(_display_lines(repo.get('upload_surfaces')), limit=4)}")
        body_parts.append(f"<div class=\"card-copy\"><strong>Auth signals</strong></div>{_render_html_list(_display_lines(repo.get('auth_signals')), limit=4)}")
        _render_html_card("section-card", "Repository evidence", "Key repository-level signals feeding the council review.", "".join(body_parts))

    with columns[1]:
        body_parts = []
        if source_turns:
            body_parts.append(f"<div class=\"card-copy\">Conversation input supplied {len(source_turns)} turn(s).</div>")
            body_parts.append("<ul class=\"card-list\">")
            for turn in source_turns[:4]:
                role = _escape(_display_text(turn.get("role"), "user").capitalize())
                content = _escape(_display_text(turn.get("content"), "").strip()[:220])
                if content:
                    body_parts.append(f"<li><strong>{role}</strong>: {content}</li>")
            body_parts.append("</ul>")
        else:
            body_parts.append("<div class=\"card-copy\">No conversation turns were returned in the payload.</div>")
        if behavior:
            body_parts.append(f"<div class=\"card-copy\"><strong>Content markers</strong></div>{_render_html_list(_display_lines(behavior.get('content_markers')), limit=4)}")
            body_parts.append(f"<div class=\"card-copy\"><strong>Key signals</strong></div>{_render_html_list(_display_lines(behavior.get('key_signals')), limit=4)}")
            body_parts.append(f"<div class=\"card-copy\"><strong>Risk notes</strong></div>{_render_html_list(_display_lines(behavior.get('risk_notes')), limit=4)}")
        _render_html_card("section-card", "Behavior evidence", "Observed transcript and behavior markers attached to this evaluation.", "".join(body_parts))


def _stakeholder_takeaways(expert: dict, result: dict, workflow: str) -> list[str]:
    expert_name = _display_text(expert.get("expert_name"), "")
    repo = result.get("repository_summary") or {}
    expert_input = result.get("expert_input") or {}
    upload_path = _upload_path(repo, expert)
    backend_label = _backend_label(repo)
    has_no_auth = "no_explicit_auth" in {str(item) for item in _display_lines(repo.get("auth_signals"))}
    has_transcript = workflow in {"Behavior-only", "Hybrid"}
    findings_text = " ".join(str(item) for item in expert.get("findings", [])).lower()

    if expert_name == "team1_policy_expert":
        if repo:
            if workflow == "Hybrid":
                lines = [f"This hybrid review checks whether `{upload_path}` and the conversation both show clear access, oversight, and accountability controls."]
            else:
                lines = [f"This review checks whether `{upload_path}` and the broader intake workflow have clear access, oversight, and accountability controls."]
            if has_no_auth:
                lines.append(f"No explicit access-control layer is visible around `{upload_path}`, which weakens the governance story for public intake.")
            if repo.get("llm_backends"):
                lines.append(f"Because {backend_label} process submitted content, retention, escalation, and third-party accountability expectations should be documented before sign-off.")
        elif has_transcript:
            lines = ["This review checks the transcript for oversight, escalation, and refusal behavior."]
            lines.append("The policy lens looks for whether the conversation shows clear governance, accountability, and human review behavior.")
        else:
            lines = ["This review checks whether the submission shows clear governance, accountability, and oversight behavior."]
        return lines[:3]

    if expert_name == "team2_redteam_expert":
        if repo:
            if workflow == "Hybrid":
                lines = [f"This hybrid review asks how a real attacker could misuse `{upload_path}` or manipulate the conversation in practice."]
            else:
                lines = [f"This review asks how a real attacker could misuse `{upload_path}` in practice."]
            if repo.get("llm_backends"):
                lines.append(f"The route into {backend_label} creates a concrete hostile-file or prompt-injection path before safeguards clearly stop abuse.")
            else:
                lines.append("The exposed intake workflow creates a concrete hostile-file or misuse path before safeguards clearly stop abuse.")
            lines.append("That means the repository can be operationally abused, not just theoretically criticized.")
        elif has_transcript:
            lines = ["This review asks how an attacker could manipulate the transcript or behavior trace in practice."]
            lines.append("The red-team lens looks for jailbreak, leakage, prompt-injection, and unsafe-following behavior in the observed conversation.")
        else:
            lines = ["This review asks how a real attacker could misuse the submitted behavior or repository evidence in practice."]
        return lines[:3]

    if expert_name == "team3_risk_expert":
        if repo:
            if workflow == "Hybrid":
                lines = [f"This hybrid review focuses on the deployed system boundary around `{upload_path}` and the observed conversation behavior, not only prompts or policy wording."]
            else:
                lines = [f"This review focuses on the deployed system boundary around `{upload_path}`, not only prompts or policy wording."]
            if repo.get("llm_backends"):
                lines.append(f"The same workflow combines public uploads, local media processing, and {backend_label} in one chain.")
            if has_no_auth or "secret-key" in findings_text or "secret key" in findings_text:
                lines.append("That architecture needs stronger authentication, isolation, and deployment hardening before production use.")
        elif has_transcript:
            lines = ["This review focuses on the observed system behavior boundary, not only wording in the transcript."]
            lines.append("The system lens checks whether behavior matches deployment claims, safety guardrails, and operational expectations.")
        else:
            lines = ["This review focuses on the submitted system boundary, not only prompts or policy wording."]
        return lines[:3]

    if "upload" in findings_text:
        return ["The repository exposes user-controlled input that needs stronger safety controls before approval."]
    return ["This expert found repository-specific risk signals that should be reviewed before sign-off."]


def _expert_evidence_lines(expert: dict, workflow: str, result: dict) -> list[str]:
    evidence = expert.get("evidence", {}) if isinstance(expert, dict) else {}
    expert_name = _display_text(expert.get("expert_name"), "")
    lines: list[str] = []

    if expert_name == "team1_policy_expert":
        if evidence.get("policy_scope_scan_mode") == "local_scan":
            lines.append(f"Independent policy scan across {int(evidence.get('policy_scope_scanned_file_count', 0))} files.")
        controls = _display_lines(evidence.get("policy_scope_controls"))
        if controls:
            lines.append(f"Governance controls observed: {', '.join(item.rstrip('.') for item in controls[:3])}.")
        for item in evidence.get("policy_scope_evidence", [])[:2]:
            if isinstance(item, dict):
                lines.append(f"{item.get('path', 'unknown')}: {item.get('signal', 'Policy evidence')}.")
        return lines[:3]

    if expert_name == "team2_redteam_expert":
        surface = evidence.get("redteam_surface", {})
        if isinstance(surface, dict) and surface.get("scan_mode") == "local_scan":
            lines.append(
                f"Independent red-team scan across {int(surface.get('public_route_count', 0))} public route(s) and {len(surface.get('scenario_library', []))} generated abuse scenario(s)."
            )
        taxonomy = evidence.get("taxonomy", {})
        if isinstance(taxonomy, dict):
            owasp = _display_lines(taxonomy.get("owasp_categories"))
            mitre = _display_lines(taxonomy.get("mitre_tactics"))
            if owasp:
                lines.append(f"OWASP categories: {', '.join(owasp[:3])}.")
            if mitre:
                lines.append(f"MITRE-style tactics: {', '.join(mitre[:3])}.")
        if isinstance(surface, dict):
            signals = _display_lines(surface.get("surface_signals"))
            if signals:
                lines.append(f"Threat surface signals: {', '.join(signals[:3])}.")
        if workflow in {"Behavior-only", "Hybrid"}:
            source_conversation = evidence.get("source_conversation", [])
            if isinstance(source_conversation, list) and source_conversation:
                lines.append(f"Conversation evidence supplied {len(source_conversation)} turn(s).")
        return lines[:3]

    if expert_name == "team3_risk_expert":
        if evidence.get("system_scope_scan_mode") == "local_scan":
            lines.append(f"Independent system scan across {int(evidence.get('system_scope_scanned_file_count', 0))} files.")
        for item in evidence.get("system_scope_evidence", [])[:2]:
            if isinstance(item, dict):
                lines.append(f"{item.get('path', 'unknown')}: {item.get('signal', 'System evidence')}.")
        rule_baseline = evidence.get("rule_baseline", {})
        if isinstance(rule_baseline, dict) and rule_baseline.get("risk_tier"):
            lines.append(f"Baseline deployment tier: {rule_baseline.get('risk_tier')}.")
        return lines[:3]

    return []


def _expert_icon(expert_name: str) -> str:
    icons = {
        "team1_policy_expert": "&#9878;",
        "team2_redteam_expert": "&#128737;",
        "team3_risk_expert": "&#128272;",
    }
    return icons.get(expert_name, "&#128301;")


def _expert_summary_card(expert: dict, result: dict, workflow: str) -> None:
    risk_tier = _display_text(expert.get("risk_tier"), "UNKNOWN")
    risk_class = ui_styles.risk_class(risk_tier)
    expert_name = _display_text(expert.get("expert_name"), "expert")
    status = _display_text(expert.get("evaluation_status"), "unknown")
    confidence = float(expert.get("confidence", 0.0))
    icon = _expert_icon(expert_name)

    body_parts = [
        f"<div class=\"card-copy\"><strong>Status:</strong> <code>{_escape(status)}</code></div>",
        f"<div class=\"card-copy\"><strong>Risk:</strong> <span class=\"{risk_class}\">{_escape(risk_tier)}</span></div>",
        f"<div class=\"card-copy\"><strong>Confidence:</strong> {_escape(f'{confidence:.2f}')}</div>",
        f"<div class=\"card-copy\"><strong>Bottom line:</strong> {_escape(_display_text(expert.get('summary'), 'No summary available.'))}</div>",
        "<div class=\"card-copy\"><strong>What this means</strong></div>",
        _render_html_list(_stakeholder_takeaways(expert, result, workflow), limit=3),
    ]
    evidence_lines = _expert_evidence_lines(expert, workflow, result)
    if evidence_lines:
        body_parts.append("<div class=\"card-copy\"><strong>Evidence you can trace</strong></div>")
        body_parts.append(_render_html_list(evidence_lines))
    st.markdown(
        "\n".join(
            [
                '<div class="module-card">',
                f'<h3 class="card-title">{icon}&nbsp; {_escape(_expert_title(expert_name))}</h3>',
                *[part for part in body_parts if part],
                "</div>",
            ]
        ),
        unsafe_allow_html=True,
    )
    with st.expander("Technical findings and scores", expanded=False):
        findings = _display_lines(expert.get("findings"))
        if findings:
            st.markdown("**Detailed findings**")
            for finding in findings[:6]:
                st.markdown(f"- {finding}")
        detail_payload = expert.get("detail_payload")
        if isinstance(detail_payload, dict):
            st.markdown("**Detail payload hints**")
            st.markdown(f"- Type: `{detail_payload.get('detail_type', 'generic')}`")
            st.markdown(f"- Source: `{detail_payload.get('source', 'rules')}`")
            notes = _display_lines(detail_payload.get("notes"))
            if notes:
                for note in notes[:4]:
                    st.markdown(f"- {note}")
        st.markdown(f"**Risk score:** {float(expert.get('risk_score', 0.0)):.2f}")
        metadata = expert.get("metadata")
        if isinstance(metadata, dict):
            for key in ("team", "execution_mode", "runner_mode", "configured_backend", "actual_backend", "taxonomy_label"):
                if metadata.get(key):
                    st.markdown(f"- **{key.replace('_', ' ').title()}:** {metadata.get(key)}")


def _render_expert_section(result: dict) -> None:
    experts = result.get("experts") or []
    workflow = _display_workflow(result)
    _render_html_card(
        "section-card",
        "Expert modules",
        "Three perspectives summarized in parallel before council arbitration.",
    )
    if not experts:
        st.markdown(
            """
            <div class="section-card">
                <div class="card-copy">No expert modules were returned for this evaluation.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        columns = st.columns(3)
        for idx, expert in enumerate(experts[:3]):
            with columns[idx]:
                if isinstance(expert, dict):
                    _expert_summary_card(expert, result, workflow)


def _render_council_section(result: dict) -> None:
    council = result.get("council_result") or {}
    decision = _display_text(result.get("decision"), "REVIEW")
    badge_class = _decision_badge_class(decision)
    rule_name = _decision_rule_label(_display_text(council.get("decision_rule_triggered"), ""))
    triggered_by = ", ".join(_trigger_label(str(item)) for item in council.get("triggered_by", [])) or "None"
    channel_scores = council.get("channel_scores") or {}
    disagreement_index = float(council.get("disagreement_index", 0.0))

    summary_html = (
        '<div class="pill-row">'
        f'<span class="badge {badge_class}">{_escape(decision)}</span>'
        f'<span class="pill pill-neutral">&#9878;&nbsp; {_escape(rule_name)}</span>'
        f'<span class="pill pill-neutral">&#8646;&nbsp; Disagreement {_escape(f"{disagreement_index:.2f}")}</span>'
        "</div>"
    )
    _render_html_card(
        "section-card",
        "Council synthesis",
        "Final arbitration output and the rationale that drove the disposition.",
        summary_html,
    )

    left, right = st.columns([1.1, 0.9])
    with left:
        left_parts = [
            "<div class=\"card-copy\"><strong>Rationale</strong></div>",
            f"<div class=\"card-copy\">{_escape(_display_text(council.get('rationale'), 'No rationale was returned.'))}</div>",
        ]
        if council.get("consensus_summary"):
            left_parts.append("<div class=\"card-copy\"><strong>Consensus summary</strong></div>")
            left_parts.append(f"<div class=\"card-copy\">{_escape(_display_text(council.get('consensus_summary'), ''))}</div>")
        if council.get("recommended_actions"):
            left_parts.append("<div class=\"card-copy\"><strong>Recommended actions</strong></div>")
            left_parts.append(_render_html_list(_display_lines(council.get("recommended_actions")), limit=6))
        left_parts.append("<div class=\"card-copy\"><strong>What happens next</strong></div>")
        left_parts.append(_render_html_list(_governance_next_steps(result)))
        _render_html_card("section-card", "Rationale & next steps", None, "".join(left_parts))
    with right:
        facts_html = _render_kv_grid(
            [
                ("Council score", f"{float(council.get('council_score', 0.0)):.2f}"),
                ("Score basis", _display_text(council.get("score_basis"), "expert_average")),
                ("Triggered by", triggered_by),
                ("Human review", "Yes" if council.get("needs_human_review") else "No"),
            ]
        )
        if channel_scores:
            facts_html += _render_kv_grid(
                [
                    (
                        "Channel scores",
                        f"repository {float(channel_scores.get('repository_channel_score', 0.0)):.2f} | behavior {float(channel_scores.get('behavior_channel_score', 0.0)):.2f}",
                    )
                ]
            )
        summary_lines = _deliberation_summary_lines(council)
        summary_html = ""
        if summary_lines:
            summary_html = f"<div class=\"card-copy\"><strong>How the experts challenged each other</strong></div>{_render_html_list(summary_lines)}"
        _render_html_card("section-card", "Council facts", None, facts_html + summary_html)

    with st.expander("Technical council trace", expanded=False):
        if council.get("cross_expert_critique"):
            st.markdown("**Cross-expert critique**")
            for item in _display_lines(council.get("cross_expert_critique")):
                st.markdown(f"- {item}")
        if council.get("key_evidence"):
            st.markdown("**Key evidence**")
            for item in _display_lines(council.get("key_evidence")):
                st.markdown(f"- {item}")
        if council.get("ignored_signals"):
            st.markdown("**Signals noted but not decisive**")
            for item in _display_lines(council.get("ignored_signals")):
                st.markdown(f"- {item}")
        if council.get("deliberation_trace"):
            st.markdown("**Full deliberation trace**")
            for item in council.get("deliberation_trace", []):
                if not isinstance(item, dict):
                    continue
                phase = _display_text(item.get("phase"), "").upper()
                author = _expert_title(_display_text(item.get("author_expert"), "expert"))
                target = _display_text(item.get("target_expert"), "")
                target_copy = f" -> {_expert_title(target)}" if target else ""
                st.markdown(f"- **{phase}** `{author}{target_copy}`: {_display_text(item.get('summary'), '')}")


def _governance_next_steps(result: dict) -> list[str]:
    decision = _display_text(result.get("decision"), "REVIEW")
    if decision == "REJECT":
        return [
            "Do not move this submission into production or open pilot deployment yet.",
            "Assign engineering, security, and governance owners to close the listed gaps and capture evidence of remediation.",
            "Rerun the evaluation after fixes and attach the updated report to the change-control record.",
        ]
    if decision == "REVIEW":
        return [
            "Pause deployment until a human reviewer signs off the listed mitigations.",
            "Use the expert findings and recommended actions to decide whether the case can move to APPROVE or must be sent back for remediation.",
            "Record the human decision together with this report so the governance trail stays auditable.",
        ]
    return [
        "This submission can move forward under normal change control rather than emergency escalation.",
        "Keep the current evidence trail, monitoring, and controls attached to the deployment record.",
        "If the submission scope changes materially, rerun the evaluation before the next production release.",
    ]


def _decision_copy(decision: str) -> str:
    normalized = str(decision).strip().upper()
    if normalized == "REJECT":
        return "Final outcome: block or reject."
    if normalized == "REVIEW":
        return "Manual governance review is required."
    if normalized == "APPROVE":
        return "Outcome is acceptable within the current review bounds."
    return "Council outcome generated from the current evidence mix."


def _risk_copy(risk_tier: str) -> str:
    normalized = str(risk_tier).strip().upper()
    if normalized in {"HIGH", "UNACCEPTABLE", "TIER_4", "TIER_3"}:
        return "The evaluated output carries a severe governance or safety concern."
    if normalized in {"LIMITED", "MEDIUM", "REVIEW_REQUIRED", "TIER_2"}:
        return "The output is usable only with additional review and controls."
    if normalized in {"LOW", "TIER_1"}:
        return "No major risk signal was found in this case."
    return "Risk tier synthesized from the returned expert evidence."


def _deliberation_summary_lines(council: dict) -> list[str]:
    trace = council.get("deliberation_trace", [])
    if not trace:
        return []

    lines = ["The three experts reviewed each other's blind spots before the final decision."]
    critiques = [item for item in trace if isinstance(item, dict) and item.get("phase") == "critique"]
    revisions = [item for item in trace if isinstance(item, dict) and item.get("phase") == "revision"]

    for item in critiques[:3]:
        author = _expert_title(_display_text(item.get("author_expert"), "expert"))
        target = _expert_title(_display_text(item.get("target_expert"), "expert"))
        summary = _display_text(item.get("summary"), "")
        concern = summary.split(": ", 1)[1] if ": " in summary else summary
        concern = concern.replace(_display_text(item.get("target_expert"), ""), target)
        for prefix in [f"{target} should more clearly reflect ", f"{target} did not fully account for ", f"{target} underweighted "]:
            if concern.startswith(prefix):
                concern = concern[len(prefix) :]
                break
        if concern:
            lines.append(f"{author} challenged {target} on {concern.rstrip('.')}.")
    if revisions:
        revision_summary = ", ".join(
            f"{_expert_title(_display_text(item.get('author_expert'), 'expert'))} {float(item.get('risk_delta', 0.0)):+.2f}" for item in revisions[:3]
        )
        lines.append(f"After deliberation, the risk view changed for: {revision_summary}.")
    return lines[:4]


def _upload_path(repo: dict | None, expert: dict | None = None) -> str:
    repo = repo or {}
    for path in repo.get("entrypoints", []):
        if isinstance(path, str) and "upload" in path.lower():
            return path
    evidence = expert.get("evidence", {}) if isinstance(expert, dict) else {}
    surface = evidence.get("redteam_surface", {}) if isinstance(evidence, dict) else {}
    if isinstance(surface, dict):
        for route in surface.get("route_inventory", []):
            if isinstance(route, dict) and route.get("has_upload") and route.get("path"):
                return str(route.get("path"))
    return "the intake workflow"


def _backend_label(repo: dict | None) -> str:
    repo = repo or {}
    backends = [str(item) for item in repo.get("llm_backends", []) if str(item).strip()]
    if not backends:
        return "external AI services"
    return ", ".join(backends[:3])


def _render_artifacts(result: dict) -> None:
    report_path = _display_text(result.get("report_path"), "")
    archive_path = _display_text(result.get("archive_path"), "")

    location_html = _render_kv_grid(
        [
            ("Report", report_path or "Unavailable"),
            ("Archive", archive_path or "Unavailable"),
        ]
    )
    _render_html_card("section-card", "Artifacts", "Downloadable outputs and saved paths for auditability and handoff.", location_html)

    artifact_cols = st.columns(2)
    with artifact_cols[0]:
        st.markdown(
            """
            <div class="section-card">
                <h3 class="card-title">Markdown report</h3>
                <p class="body-copy">Primary human-readable handoff for governance review.</p>
            """,
            unsafe_allow_html=True,
        )
        if report_path and Path(report_path).exists():
            st.download_button(
                "Download markdown report",
                data=Path(report_path).read_text(encoding="utf-8"),
                file_name=Path(report_path).name,
                mime="text/markdown",
                use_container_width=True,
            )
        else:
            st.markdown("Markdown report path not available or file missing.")
        st.markdown("</div>", unsafe_allow_html=True)
    with artifact_cols[1]:
        st.markdown(
            """
            <div class="section-card">
                <h3 class="card-title">Archive JSON</h3>
                <p class="body-copy">Machine-readable payload for traceability and replay.</p>
            """,
            unsafe_allow_html=True,
        )
        if archive_path and Path(archive_path).exists():
            st.download_button(
                "Download archive JSON",
                data=Path(archive_path).read_text(encoding="utf-8"),
                file_name=Path(archive_path).name,
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.markdown("Archive JSON path not available or file missing.")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_raw_response(result: dict) -> None:
    # Compact collapsible — collapsed by default so it doesn't dominate the page
    with st.expander("Raw API response — full evaluation payload (traceability)", expanded=False):
        st.caption("Full JSON returned by the backend. Expand to inspect or copy for debugging.")
        st.code(json.dumps(result, indent=2, ensure_ascii=False, default=str), language="json")


def render_result_page(result: dict | None) -> None:
    _inject_styles()

    if not result:
        st.markdown(
            """
            <div class="section-card empty-state">
                <div class="empty-title">No evaluation result yet</div>
                <div class="empty-copy">Run an evaluation first, or return to the input form to submit a repository, transcript, or hybrid review.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Back to Inputs", use_container_width=True):
            st.session_state.current_page = "input"
            st.rerun()
        return

    _render_chips(result)
    _render_action_bar(result)
    _render_metric_row(result)
    _render_overview(result)
    _render_evidence_sections(result)
    _render_expert_section(result)
    _render_council_section(result)
    _render_artifacts(result)
    _render_raw_response(result)
