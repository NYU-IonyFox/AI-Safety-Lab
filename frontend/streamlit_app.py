from __future__ import annotations

import json
from pathlib import Path

import httpx
import streamlit as st

APP_TITLE = "AI Safety Lab"
APP_SUBTITLE = "A stakeholder-facing AI safety evaluation workspace for public GitHub repositories and local codebases."
DEFAULT_API_BASE = "http://127.0.0.1:8080"
DEFAULT_GITHUB_TARGET = ""
DEFAULT_LOCAL_TARGET = ""
DEFAULT_DESCRIPTION = "Repository submission for AI safety review."

EXPERT_TITLES = {
    "team1_policy_expert": "Policy & Compliance",
    "team2_redteam_expert": "Adversarial Misuse",
    "team3_risk_expert": "System & Deployment",
}

TRIGGER_LABELS = {
    "team1_policy_expert": "Policy & Compliance",
    "team2_redteam_expert": "Adversarial Misuse",
    "team3_risk_expert": "System & Deployment",
    "disagreement": "Expert disagreement",
}

DECISION_RULE_LABELS = {
    "critical_fail_closed": "Critical fail-closed trigger",
    "policy_and_misuse_alignment": "Policy and misuse experts aligned on high risk",
    "expert_failure_review": "Expert failure requires human review",
    "critical_expert_degraded": "Critical expert degraded",
    "multi_expert_high_risk": "Multiple experts reached high risk",
    "system_risk_review": "System-risk expert forced review",
    "low_confidence_review": "Low confidence requires review",
    "expert_disagreement_review": "Expert disagreement requires review",
    "moderate_risk_review": "Moderate risk requires review",
    "baseline_approve": "Baseline approval threshold met",
    "no_experts": "No expert outputs available",
}

st.set_page_config(page_title=APP_TITLE, page_icon="🛡️", layout="wide")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(241, 90, 36, 0.08), transparent 30%),
                linear-gradient(180deg, #f5f1e8 0%, #f2efe8 100%);
            color: #1e293b;
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        .hero-card, .section-card, .expert-card, .metric-card, .step-card {
            background: rgba(255, 252, 247, 0.94);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 22px;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
            padding: 1.1rem 1.2rem;
            margin-bottom: 1rem;
        }
        .hero-card {
            padding: 1.35rem 1.35rem;
        }
        .hero-title {
            font-size: 2.15rem;
            line-height: 1.05;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.35rem;
        }
        .hero-copy {
            color: #475569;
            font-size: 1rem;
            line-height: 1.55;
        }
        .hero-grid {
            display: grid;
            grid-template-columns: 1.4fr 1fr;
            gap: 1rem;
            align-items: start;
        }
        .hero-list {
            margin: 0.7rem 0 0 0;
            padding-left: 1.15rem;
            color: #334155;
            line-height: 1.6;
        }
        .score-strip {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.8rem;
            margin-top: 0.9rem;
        }
        .mini-stat {
            border-radius: 18px;
            background: #fffaf4;
            border: 1px solid rgba(148, 163, 184, 0.22);
            padding: 0.85rem 0.9rem;
        }
        .mini-stat-label {
            font-size: 0.78rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .mini-stat-value {
            font-size: 1.25rem;
            font-weight: 800;
            color: #0f172a;
            margin-top: 0.25rem;
        }
        .metric-card {
            min-height: 150px;
            border-left: 8px solid transparent;
        }
        .step-card {
            min-height: 170px;
        }
        .tone-red { background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%); border-left-color: #e11d48; }
        .tone-yellow { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-left-color: #d97706; }
        .tone-green { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-left-color: #16a34a; }
        .tone-blue { background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left-color: #2563eb; }
        .pill {
            display: inline-block;
            padding: 0.30rem 0.65rem;
            border-radius: 999px;
            background: #e2e8f0;
            color: #334155;
            font-size: 0.82rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }
        .muted { color: #64748b; }
        @media (max-width: 900px) {
            .hero-grid, .score-strip {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_state() -> None:
    st.session_state.setdefault("evaluation_result", None)


def tone_for_decision(decision: str) -> str:
    if decision == "REJECT":
        return "tone-red"
    if decision == "REVIEW":
        return "tone-yellow"
    return "tone-green"


def risk_tone(risk_tier: str) -> str:
    tier = risk_tier.upper()
    if tier in {"UNACCEPTABLE", "HIGH", "TIER_4", "TIER_3"}:
        return "tone-red"
    if tier in {"LIMITED", "REVIEW_REQUIRED", "TIER_2"}:
        return "tone-yellow"
    return "tone-green"


def expert_title(expert_name: str) -> str:
    return EXPERT_TITLES.get(expert_name, expert_name)


def trigger_label(trigger: str) -> str:
    return TRIGGER_LABELS.get(trigger, trigger.replace("_", " "))


def decision_rule_label(rule_name: str) -> str:
    if not rule_name:
        return "Unspecified"
    return DECISION_RULE_LABELS.get(rule_name, rule_name.replace("_", " "))


def expert_evidence_lines(expert: dict) -> list[str]:
    evidence = expert.get("evidence", {}) if isinstance(expert, dict) else {}
    expert_name = str(expert.get("expert_name", ""))

    if expert_name == "team1_policy_expert":
        lines = []
        controls = [str(item) for item in evidence.get("policy_scope_controls", []) if str(item).strip()]
        if controls:
            lines.append(f"Governance controls observed: {', '.join(controls[:3])}.")
        for item in evidence.get("policy_scope_evidence", [])[:2]:
            if isinstance(item, dict):
                lines.append(f"{item.get('path', 'unknown')}: {item.get('signal', 'Policy evidence')}.")
        return lines[:3]

    if expert_name == "team2_redteam_expert":
        lines = []
        taxonomy = evidence.get("taxonomy", {})
        if isinstance(taxonomy, dict):
            owasp = [str(item) for item in taxonomy.get("owasp_categories", []) if str(item).strip()]
            mitre = [str(item) for item in taxonomy.get("mitre_tactics", []) if str(item).strip()]
            if owasp:
                lines.append(f"OWASP categories: {', '.join(owasp[:3])}.")
            if mitre:
                lines.append(f"MITRE-style tactics: {', '.join(mitre[:3])}.")
        surface = evidence.get("redteam_surface", {})
        if isinstance(surface, dict):
            signals = [str(item) for item in surface.get("surface_signals", []) if str(item).strip()]
            if signals:
                lines.append(f"Threat surface signals: {', '.join(signals[:3])}.")
        return lines[:3]

    if expert_name == "team3_risk_expert":
        lines = []
        for item in evidence.get("system_scope_evidence", [])[:2]:
            if isinstance(item, dict):
                lines.append(f"{item.get('path', 'unknown')}: {item.get('signal', 'System evidence')}.")
        rule_baseline = evidence.get("rule_baseline", {})
        if isinstance(rule_baseline, dict) and rule_baseline.get("risk_tier"):
            lines.append(f"Baseline deployment tier: {rule_baseline.get('risk_tier')}.")
        return lines[:3]

    return []


def render_metric(label: str, value: str, tone: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div class="muted"><strong>{label}</strong></div>
            <div style="font-size:1.35rem;font-weight:800;margin-top:0.35rem;">{value}</div>
            <div style="margin-top:0.45rem;">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_payload(
    source_type: str,
    github_url: str,
    local_path: str,
    target_name: str,
    description: str,
    target_endpoint: str,
    target_model: str,
) -> dict:
    payload = {
        "context": {
            "agent_name": target_name or "Submitted Repository",
            "description": description,
            "domain": "Other",
            "capabilities": [],
            "high_autonomy": False,
        },
        "selected_policies": ["eu_ai_act", "us_nist", "iso", "unesco"],
        "conversation": [],
        "metadata": {},
        "submission": {
            "source_type": source_type,
            "github_url": github_url.strip(),
            "local_path": local_path.strip(),
            "target_name": target_name.strip(),
            "description": description.strip(),
        },
    }
    if target_endpoint.strip():
        payload["metadata"]["target_endpoint"] = target_endpoint.strip()
    if target_model.strip():
        payload["metadata"]["target_model"] = target_model.strip()
    return payload


def submit_evaluation(api_base: str, payload: dict) -> dict:
    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{api_base.rstrip('/')}/v1/evaluations", json=payload)
        response.raise_for_status()
        return response.json()


def render_intro() -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-grid">
                <div>
                    <div class="hero-title">{APP_TITLE}</div>
                    <div class="hero-copy">{APP_SUBTITLE}</div>
                    <div style="margin-top:0.8rem;">
                        <span class="pill">GitHub URL or local path</span>
                        <span class="pill">three experts + council</span>
                        <span class="pill">stakeholder-ready report</span>
                    </div>
                    <ul class="hero-list">
                        <li>Submit a real repository and extract framework, upload, auth, and LLM signals.</li>
                        <li>Compare three distinct expert lenses instead of one generic score.</li>
                        <li>Return a final APPROVE / REVIEW / REJECT decision with an explicit arbitration rule.</li>
                    </ul>
                </div>
                <div>
                    <div class="section-card" style="margin-bottom:0; background:#fffaf4;">
                        <div class="muted"><strong>Suggested workflow</strong></div>
                        <div style="margin-top:0.45rem; font-weight:700; color:#0f172a;">1. Start backend and frontend locally</div>
                        <div class="muted">2. Submit a public GitHub repository or a local codebase</div>
                        <div class="muted">3. Review the expert findings, arbitration rule, and stakeholder report</div>
                    </div>
                </div>
            </div>
            <div class="score-strip">
                <div class="mini-stat">
                    <div class="mini-stat-label">D1 Executability</div>
                    <div class="mini-stat-value">Clean-machine</div>
                </div>
                <div class="mini-stat">
                    <div class="mini-stat-label">D2 Functional fitness</div>
                    <div class="mini-stat-value">Repo-specific</div>
                </div>
                <div class="mini-stat">
                    <div class="mini-stat-label">D3/D4 Output quality</div>
                    <div class="mini-stat-value">Stakeholder-ready</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_demo_steps() -> None:
    st.subheader("Demo flow")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="step-card">
                <div class="muted"><strong>Step 1</strong></div>
                <div style="font-size:1.15rem;font-weight:800;margin-top:0.2rem;">Choose the repository source</div>
                <div style="margin-top:0.45rem;">Use a public GitHub URL for the smoothest demo path, or switch to a local path for offline debugging.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="step-card">
                <div class="muted"><strong>Step 2</strong></div>
                <div style="font-size:1.15rem;font-weight:800;margin-top:0.2rem;">Run the evaluation</div>
                <div style="margin-top:0.45rem;">The backend analyzes the repository, enriches expert input, and synthesizes an explicit council decision.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
            <div class="step-card">
                <div class="muted"><strong>Step 3</strong></div>
                <div style="font-size:1.15rem;font-weight:800;margin-top:0.2rem;">Review the stakeholder output</div>
                <div style="margin-top:0.45rem;">Inspect expert differences, repository evidence, the arbitration rule, and downloadable artifacts.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_submission_form() -> None:
    render_intro()
    render_demo_steps()

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Repository submission")
        source_options = {
            "Public GitHub repository (recommended)": "github_url",
            "Local folder on this machine": "local_path",
        }
        source_label = st.radio("Choose what to review", list(source_options.keys()), horizontal=True)
        source_type = source_options[source_label]
        github_url = ""
        local_path = ""
        if source_type == "github_url":
            github_url = st.text_input("GitHub URL", value=DEFAULT_GITHUB_TARGET, placeholder="https://github.com/owner/repository")
            st.caption("Recommended for the smoothest evaluation flow. Paste a public repository link and run the review.")
        else:
            local_path = st.text_input("Local folder path", value=DEFAULT_LOCAL_TARGET, placeholder="/absolute/path/to/repository")
            st.caption("Use this for local debugging or offline review on the same machine as the backend.")

        with st.expander("Optional labels", expanded=False):
            target_name = st.text_input("Display name", value="Submitted Repository")
            description = st.text_area("Short description", value=DEFAULT_DESCRIPTION, height=90)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("What the user will see")
        st.markdown("- Repository summary grounded in the submitted codebase")
        st.markdown("- Three distinct expert assessments")
        st.markdown("- Explicit arbitration rule for APPROVE / REVIEW / REJECT")
        st.markdown("- Downloadable stakeholder report and JSON archive")
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Advanced settings for local debugging", expanded=False):
        api_base = st.text_input("Backend API base", value=DEFAULT_API_BASE)
        target_endpoint = st.text_input("LLM endpoint (optional)", value="")
        target_model = st.text_input("Model name (optional)", value="")
        st.caption("Most users can leave this closed. These fields are only needed for custom backend routing or target execution.")

    if st.button("Run evaluation", use_container_width=True):
        if source_type == "local_path" and not local_path.strip():
            st.warning("Please provide a local path.")
            return
        if source_type == "github_url" and not github_url.strip():
            st.warning("Please provide a GitHub URL.")
            return

        payload = build_payload(source_type, github_url, local_path, target_name, description, target_endpoint, target_model)
        with st.spinner("Running expert evaluation..."):
            try:
                st.session_state.evaluation_result = submit_evaluation(api_base, payload)
            except httpx.HTTPStatusError as exc:
                st.error(f"Backend returned {exc.response.status_code}: {exc.response.text}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Evaluation failed: {exc}")


def render_repository_summary(repo: dict) -> None:
    st.subheader("Target summary")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown(f"**Target:** {repo.get('target_name', 'Unknown')}")
        st.markdown(f"**Framework:** {repo.get('framework', 'Unknown')}")
        st.markdown(f"**Source type:** {repo.get('source_type', 'manual')}")
        st.markdown(f"**Summary:** {repo.get('summary', 'No summary available.')}")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("**Detected signals**")
        for item in repo.get("detected_signals", []):
            st.markdown(f"- {item}")
        st.markdown("**Risk notes**")
        for item in repo.get("risk_notes", []):
            st.markdown(f"- {item}")
        st.markdown("</div>", unsafe_allow_html=True)

    evidence_items = repo.get("evidence_items", [])
    if evidence_items:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("**Evidence from repository**")
        for item in evidence_items[:6]:
            st.markdown(
                f"- `{item.get('path', 'unknown')}`: **{item.get('signal', 'Signal')}**. {item.get('why_it_matters', '')}"
            )
        st.markdown("</div>", unsafe_allow_html=True)


def render_expert_panels(experts: list[dict]) -> None:
    st.subheader("Three expert modules")
    columns = st.columns(3)
    for idx, expert in enumerate(experts[:3]):
        with columns[idx]:
            tone = risk_tone(expert.get("risk_tier", "UNKNOWN"))
            st.markdown(f"<div class='expert-card {tone}'>", unsafe_allow_html=True)
            st.markdown(f"### {expert_title(expert.get('expert_name', 'expert'))}")
            st.markdown(f"**Risk tier:** {expert.get('risk_tier', 'UNKNOWN')}")
            st.markdown(f"**Bottom line:** {expert.get('summary', '')}")
            st.markdown("**Findings**")
            for finding in expert.get("findings", [])[:8]:
                st.markdown(f"- {finding}")
            evidence_lines = expert_evidence_lines(expert)
            if evidence_lines:
                st.markdown("**Expert-specific evidence**")
                for item in evidence_lines:
                    st.markdown(f"- {item}")
            with st.expander("Technical details", expanded=False):
                st.markdown(f"**Status:** `{expert.get('evaluation_status', 'unknown')}`")
                st.markdown(f"**Risk score:** {expert.get('risk_score', 0):.2f}")
                st.markdown(f"**Confidence:** {expert.get('confidence', 0):.2f}")
            st.markdown("</div>", unsafe_allow_html=True)


def render_council_panel(result: dict) -> None:
    council = result["council_result"]
    tone = tone_for_decision(result["decision"])
    rule_name = decision_rule_label(council.get("decision_rule_triggered", ""))
    triggered_by = ", ".join(trigger_label(item) for item in council.get("triggered_by", [])) or "None"

    st.subheader("Council synthesis")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric("Final decision", result["decision"], tone, council.get("rationale", ""))
    with c2:
        render_metric("Arbitration rule", rule_name, "tone-blue", "Explicit council rule that drove the final verdict.")
    with c3:
        render_metric("Disagreement", f"{council.get('disagreement_index', 0):.2f}", "tone-blue", "Cross-expert divergence indicator.")

    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown(f"**Rationale:** {council.get('rationale', '')}")
    if council.get("consensus_summary"):
        st.markdown(f"**Consensus summary:** {council.get('consensus_summary', '')}")
    st.markdown(f"**Council score:** {council.get('council_score', 0):.2f}")
    st.markdown(f"**Triggered by:** {triggered_by}")
    if council.get("cross_expert_critique"):
        st.markdown("**Cross-expert critique**")
        for item in council.get("cross_expert_critique", []):
            st.markdown(f"- {item}")
    if council.get("key_evidence"):
        st.markdown("**Key evidence**")
        for item in council.get("key_evidence", []):
            st.markdown(f"- {item}")
    if council.get("recommended_actions"):
        st.markdown("**Recommended actions**")
        for item in council.get("recommended_actions", []):
            st.markdown(f"- {item}")
    if council.get("ignored_signals"):
        st.markdown("**Signals that were noted but not decisive**")
        for item in council.get("ignored_signals", []):
            st.markdown(f"- {item}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_artifacts(result: dict) -> None:
    st.subheader("Artifacts")
    report_path = result.get("report_path", "")
    archive_path = result.get("archive_path", "")
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    if report_path and Path(report_path).exists():
        st.download_button(
            "Download markdown report",
            data=Path(report_path).read_text(encoding="utf-8"),
            file_name=Path(report_path).name,
            mime="text/markdown",
            use_container_width=True,
        )
    if archive_path and Path(archive_path).exists():
        st.download_button(
            "Download archive JSON",
            data=Path(archive_path).read_text(encoding="utf-8"),
            file_name=Path(archive_path).name,
            mime="application/json",
            use_container_width=True,
        )
    with st.expander("Saved artifact locations", expanded=False):
        st.markdown(f"**Readable report:** `{report_path}`")
        st.markdown(f"**Archive JSON:** `{archive_path}`")
    st.markdown("</div>", unsafe_allow_html=True)


def render_result() -> None:
    result = st.session_state.evaluation_result
    if not result:
        return

    render_repository_summary(result.get("repository_summary", {}))
    render_expert_panels(result.get("experts", []))
    render_council_panel(result)
    render_artifacts(result)

    with st.expander("Show raw API response", expanded=False):
        st.code(json.dumps(result, indent=2, ensure_ascii=False), language="json")


def main() -> None:
    inject_styles()
    ensure_state()
    render_submission_form()
    render_result()


if __name__ == "__main__":
    main()
