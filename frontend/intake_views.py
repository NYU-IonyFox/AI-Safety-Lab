from __future__ import annotations

import html
from typing import Callable

import httpx
import streamlit as st


DEFAULT_API_BASE = "http://127.0.0.1:8080"
DEFAULT_GITHUB_TARGET = ""
DEFAULT_LOCAL_TARGET = ""
DEFAULT_DESCRIPTION = "Repository submission for AI safety review."
DEFAULT_TRANSCRIPT = ""
PENDING_SAMPLE_KEY = "_pending_sample"


def _inject_styles() -> None:
    return None


def _ensure_state() -> None:
    st.session_state.setdefault("current_page", "input")
    st.session_state.setdefault("evaluation_result", None)
    st.session_state.setdefault("workflow_mode", "Repository-only")
    st.session_state.setdefault("submitted_workflow_mode", "Repository-only")
    st.session_state.setdefault("repository_source_label", "Public GitHub repository (recommended)")
    st.session_state.setdefault("github_url_input", DEFAULT_GITHUB_TARGET)
    st.session_state.setdefault("local_path_input", DEFAULT_LOCAL_TARGET)
    st.session_state.setdefault("target_name_input", "Submitted Repository")
    st.session_state.setdefault("description_input", DEFAULT_DESCRIPTION)
    st.session_state.setdefault("transcript_input", DEFAULT_TRANSCRIPT)
    st.session_state.setdefault("api_base_input", DEFAULT_API_BASE)
    st.session_state.setdefault("target_endpoint_input", "")
    st.session_state.setdefault("target_model_input", "")
    _apply_pending_sample()


def _apply_pending_sample() -> None:
    pending_sample = st.session_state.pop(PENDING_SAMPLE_KEY, "")
    if pending_sample == "public_repo":
        _load_sample_public_repo()
    elif pending_sample == "transcript":
        _load_sample_transcript()


def _load_sample_public_repo() -> None:
    st.session_state.current_page = "input"
    st.session_state.evaluation_result = None
    st.session_state.workflow_mode = "Repository-only"
    st.session_state.submitted_workflow_mode = "Repository-only"
    st.session_state.repository_source_label = "Public GitHub repository (recommended)"
    st.session_state.github_url_input = "https://github.com/openai/openai-quickstart-python"
    st.session_state.local_path_input = DEFAULT_LOCAL_TARGET
    st.session_state.target_name_input = "OpenAI Quickstart"
    st.session_state.description_input = "Small public Python quickstart repository that calls an external LLM API."
    st.session_state.transcript_input = ""


def _load_sample_transcript() -> None:
    st.session_state.current_page = "input"
    st.session_state.evaluation_result = None
    st.session_state.workflow_mode = "Behavior-only"
    st.session_state.submitted_workflow_mode = "Behavior-only"
    st.session_state.repository_source_label = "Public GitHub repository (recommended)"
    st.session_state.github_url_input = ""
    st.session_state.local_path_input = ""
    st.session_state.target_name_input = "Sample Transcript"
    st.session_state.description_input = "Transcript submitted for behavior-only review."
    st.session_state.transcript_input = "User: Summarize the requested task.\nAssistant: I can summarize the task and explain the safety checks."


def _queue_sample(sample_name: str) -> None:
    st.session_state[PENDING_SAMPLE_KEY] = sample_name


def _escape(text: object) -> str:
    return html.escape("" if text is None else str(text))


def _render_card_header(title: str, copy: str | None = None) -> None:
    st.markdown(f'<h3 class="card-title">{title}</h3>', unsafe_allow_html=True)
    if copy:
        st.markdown(f'<p class="body-copy">{copy}</p>', unsafe_allow_html=True)


def _render_field_label(label: str) -> None:
    st.markdown(f'<div class="field-label">{label}</div>', unsafe_allow_html=True)


def _render_field_help(copy: str) -> None:
    st.markdown(f'<p class="field-help">{copy}</p>', unsafe_allow_html=True)


def _render_card(title: str, lines: list[str]) -> None:
    items = "".join(f"<li>{_escape(line)}</li>" for line in lines if str(line).strip())
    st.markdown(
        f"""
        <div class="sidebar-card">
            <h3 class="card-title">{_escape(title)}</h3>
            <ul class="card-list">{items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_sample_result() -> dict:
    return {
        "evaluation_id": "sample-eval-quickstart-001",
        "decision": "REVIEW",
        "submission": {
            "source_type": "github_url",
            "target_name": "OpenAI Quickstart",
            "description": "Minimal public Python quickstart that calls an external LLM API",
        },
        "repository_summary": {
            "target_name": "OpenAI Quickstart",
            "framework": "Flask",
            "source_type": "github_url",
            "summary": "Public quickstart repository with a simple web flow that forwards user input to an external model backend.",
            "detected_signals": [
                "Flask architecture detected",
                "External LLM backend usage detected",
                "Public request-handling route detected",
            ],
            "risk_notes": [
                "Repository accepts user-controlled prompts before downstream model execution.",
                "Operational controls and escalation guidance are not obvious from the minimal sample.",
            ],
            "notable_files": [
                "app.py",
                "templates/index.html",
                "requirements.txt",
            ],
            "evidence_items": [
                {
                    "path": "app.py:42",
                    "signal": "Request handler forwards user input to a model client",
                    "why_it_matters": "This is the main intake path and should be assessed for abuse, prompt-injection, and safety controls.",
                },
                {
                    "path": "templates/index.html:12",
                    "signal": "Public form posts directly into the application flow",
                    "why_it_matters": "Public input surfaces widen the attack surface and affect deployment risk.",
                },
            ],
            "llm_backends": ["OpenAI API"],
            "upload_surfaces": ["Prompt text submitted through the web form"],
            "auth_signals": ["no_explicit_auth"],
            "entrypoints": ["/"],
        },
        "expert_input": {
            "source_conversation": [
                {"role": "user", "content": "Please summarize the task and suggest code changes."},
                {"role": "assistant", "content": "I can review the repository path, summarize the flow, and propose changes."},
            ]
        },
        "behavior_summary": {
            "evaluation_mode": "hybrid",
            "detected_languages": ["eng_Latn"],
            "primary_language": "English",
            "translation_confidence": 0.98,
            "uncertainty_flag": False,
            "transcript_present": True,
            "content_markers": [
                "repository_summary_present",
                "target asks for code review",
            ],
            "key_signals": [
                "public_input_path_present",
                "external_model_dependency_present",
            ],
            "risk_notes": [
                "Transcript is operationally benign, but the repository still presents a reviewable intake surface."
            ],
        },
        "experts": [
            {
                "expert_name": "team1_policy_expert",
                "evaluation_status": "success",
                "risk_tier": "LIMITED",
                "confidence": 0.84,
                "risk_score": 0.46,
                "summary": "Governance review found a real submission path but limited visible policy and oversight context.",
                "findings": [
                    "No explicit governance or escalation policy is visible in the primary repository path.",
                    "External model processing should be documented for stakeholder review.",
                ],
                "evidence": {
                    "policy_scope_scan_mode": "local_scan",
                    "policy_scope_scanned_file_count": 8,
                    "policy_scope_controls": ["basic logging", "manual review expectation"],
                    "policy_scope_evidence": [
                        {"path": "README.md", "signal": "Minimal operational guidance"},
                        {"path": "app.py", "signal": "User request flows into model invocation"},
                    ],
                },
                "metadata": {
                    "team": "team1",
                    "execution_mode": "rules",
                    "runner_mode": "rules",
                    "configured_backend": "mock",
                    "actual_backend": "mock",
                },
            },
            {
                "expert_name": "team2_redteam_expert",
                "evaluation_status": "success",
                "risk_tier": "HIGH",
                "confidence": 0.88,
                "risk_score": 0.72,
                "summary": "Red-team review sees a concrete prompt-abuse path through the public intake flow into the downstream model.",
                "findings": [
                    "The public route can carry attacker-controlled content directly into model processing.",
                    "There is no obvious authentication or rate-limiting layer on the visible path.",
                ],
                "evidence": {
                    "redteam_surface": {
                        "scan_mode": "local_scan",
                        "public_route_count": 1,
                        "scenario_library": ["prompt-injection", "resource abuse"],
                        "surface_signals": ["public route", "external model dependency"],
                    },
                    "taxonomy": {
                        "owasp_categories": ["LLM01 Prompt Injection", "LLM06 Excessive Agency"],
                        "mitre_tactics": ["Initial Access", "Execution"],
                    },
                    "source_conversation": [
                        {"role": "user", "content": "Please summarize the task and suggest code changes."}
                    ],
                },
                "metadata": {
                    "team": "team2",
                    "execution_mode": "rules",
                    "runner_mode": "rules",
                    "configured_backend": "mock",
                    "actual_backend": "mock",
                },
            },
            {
                "expert_name": "team3_risk_expert",
                "evaluation_status": "success",
                "risk_tier": "TIER_2",
                "confidence": 0.81,
                "risk_score": 0.58,
                "summary": "System review found a straightforward architecture, but the deployment boundary still needs stronger control assumptions before approval.",
                "findings": [
                    "Public request intake and external model execution share one simple operational path.",
                    "The visible implementation leaves authentication and deployment hardening assumptions implicit.",
                ],
                "evidence": {
                    "system_scope_scan_mode": "local_scan",
                    "system_scope_scanned_file_count": 8,
                    "system_scope_evidence": [
                        {"path": "app.py", "signal": "Single service handles intake and model execution"},
                        {"path": "requirements.txt", "signal": "External API client dependency present"},
                    ],
                    "rule_baseline": {"risk_tier": "TIER_2"},
                },
                "metadata": {
                    "team": "team3",
                    "execution_mode": "rules",
                    "runner_mode": "rules",
                    "configured_backend": "mock",
                    "actual_backend": "mock",
                },
            },
        ],
        "council_result": {
            "decision": "REVIEW",
            "needs_human_review": True,
            "council_score": 0.61,
            "disagreement_index": 0.22,
            "score_basis": "hybrid_channel_blend",
            "decision_rule_triggered": "hybrid_cross_channel_review",
            "triggered_by": ["team2_redteam_expert", "disagreement"],
            "rationale": "The repository exposes a real public intake path into downstream model processing, but the evidence does not justify an automatic reject without a deeper human review of controls and intended deployment scope.",
            "consensus_summary": "The experts aligned on a meaningful review requirement, with the strongest concern coming from misuse and operational abuse rather than a proven catastrophic failure.",
            "recommended_actions": [
                "Add explicit authentication, rate limits, and abuse monitoring around public intake.",
                "Document escalation, retention, and operator review expectations before deployment.",
                "Re-run the evaluation after deployment controls are clarified.",
            ],
            "channel_scores": {
                "repository_channel_score": 0.68,
                "behavior_channel_score": 0.41,
                "blended_score": 0.61,
            },
            "cross_expert_critique": [
                "Team2 argued that the public route creates a concrete prompt-abuse path before visible safeguards stop misuse.",
                "Team1 noted that governance and oversight controls are not explicit enough for clean approval.",
            ],
            "key_evidence": [
                "Public request path enters downstream model processing.",
                "No explicit authentication layer is visible on the primary flow.",
            ],
            "ignored_signals": [
                "The transcript itself is benign and does not show unsafe assistant behavior."
            ],
            "deliberation_trace": [
                {
                    "phase": "critique",
                    "author_expert": "team2_redteam_expert",
                    "target_expert": "team1_policy_expert",
                    "summary": "team1_policy_expert should more clearly reflect the operational abuse path created by the public route.",
                },
                {
                    "phase": "revision",
                    "author_expert": "team3_risk_expert",
                    "target_expert": "",
                    "summary": "Adjusted deployment view after cross-expert discussion.",
                    "risk_delta": 0.08,
                },
            ],
        },
        "report_path": "data/reports/sample-eval-quickstart-001.md",
        "archive_path": "data/reports/sample-eval-quickstart-001.json",
    }


def _load_sample_result() -> None:
    st.session_state.evaluation_result = _build_sample_result()
    st.session_state.current_page = "result"


def render_sidebar(app_title: str, app_subtitle: str) -> None:
    _inject_styles()
    _ensure_state()

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-card" style="border-left:4px solid #f15a24;">
                <div class="sidebar-eyebrow">&#128737; Stakeholder Intake</div>
                <div class="sidebar-title">{app_title}</div>
                <div class="body-copy" style="margin-top:0.3rem;font-size:0.85rem;">{app_subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#64748b;margin:0.6rem 0 0.35rem 0;">Navigation</div>',
            unsafe_allow_html=True,
        )
        nav_left, nav_right = st.columns(2)
        with nav_left:
            if st.button("Inputs", use_container_width=True):
                st.session_state.current_page = "input"
                st.rerun()
        with nav_right:
            has_result = st.session_state.get("evaluation_result") is not None
            if st.button("Result", use_container_width=True, disabled=not has_result):
                st.session_state.current_page = "result"
                st.rerun()

        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#64748b;margin:0.6rem 0 0.35rem 0;">Advanced settings</div>',
            unsafe_allow_html=True,
        )
        st.text_input(
            "Backend API base",
            value=st.session_state.get("api_base_input", DEFAULT_API_BASE),
            key="api_base_input",
        )
        st.text_input(
            "Target endpoint (optional, advanced)",
            value=st.session_state.get("target_endpoint_input", ""),
            key="target_endpoint_input",
        )
        st.text_input(
            "Target model label (optional)",
            value=st.session_state.get("target_model_input", ""),
            key="target_model_input",
        )
        st.caption("Use target probing only if you want the system to generate prompts against a live or test endpoint.")

        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#64748b;margin:0.6rem 0 0.35rem 0;">Preview</div>',
            unsafe_allow_html=True,
        )
        if st.button("View Sample Result", use_container_width=True):
            _load_sample_result()
            st.rerun()


def _render_hero(app_title: str, app_subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-eyebrow">Review Intake</div>
            <div class="hero-title">&#128737;&nbsp; {app_title}</div>
            <div class="hero-copy">{app_subtitle}</div>
            <div class="hero-pill-row">
                <span class="pill">&#128196;&nbsp; Repository-only</span>
                <span class="pill">&#128172;&nbsp; Behavior-only</span>
                <span class="pill">&#9889;&nbsp; Hybrid</span>
                <span class="pill pill-neutral">3 experts + council</span>
                <span class="pill pill-green">Stakeholder-ready report</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_context_cards() -> None:
    left, right = st.columns([1.3, 1])
    with left:
        st.markdown(
            """
            <div class="section-card">
                <h3 class="card-title">Review Scope</h3>
                <p class="body-copy" style="margin-bottom:0.8rem;">Submit a repository, a transcript, or both. Three expert modules then evaluate in parallel.</p>
                <div class="step-row">
                    <div class="step-num" style="background:linear-gradient(135deg,#7c3aed,#6d28d9);font-size:0.9rem;">&#128196;</div>
                    <div class="step-body">
                        <div class="step-title">Repository-only</div>
                        <div class="step-copy">Public GitHub URL or local folder on the backend machine.</div>
                    </div>
                </div>
                <div class="step-row">
                    <div class="step-num" style="background:linear-gradient(135deg,#0891b2,#0e7490);font-size:0.9rem;">&#128172;</div>
                    <div class="step-body">
                        <div class="step-title">Behavior-only</div>
                        <div class="step-copy">Conversation transcript or interaction log mapped to the evaluation pipeline.</div>
                    </div>
                </div>
                <div class="step-row" style="margin-bottom:0;">
                    <div class="step-num" style="background:linear-gradient(135deg,#f15a24,#dc4b10);font-size:0.9rem;">&#9889;</div>
                    <div class="step-body">
                        <div class="step-title">Hybrid</div>
                        <div class="step-copy">Repository evidence + transcript evidence in one unified council evaluation.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="section-card">
                <h3 class="card-title">How it works</h3>
                <div class="step-row">
                    <div class="step-num">1</div>
                    <div class="step-body">
                        <div class="step-title">Choose a review mode</div>
                        <div class="step-copy">Repository-only, Behavior-only, or Hybrid.</div>
                    </div>
                </div>
                <div class="step-row">
                    <div class="step-num">2</div>
                    <div class="step-body">
                        <div class="step-title">Add evidence</div>
                        <div class="step-copy">Paste a GitHub URL, a local path, a transcript, or both.</div>
                    </div>
                </div>
                <div class="step-row">
                    <div class="step-num">3</div>
                    <div class="step-body">
                        <div class="step-title">Run the council</div>
                        <div class="step-copy">Three expert modules evaluate in parallel, then synthesize a final verdict.</div>
                    </div>
                </div>
                <div class="step-row" style="margin-bottom:0;">
                    <div class="step-num">4</div>
                    <div class="step-body">
                        <div class="step-title">Review findings</div>
                        <div class="step-copy">Expert modules, arbitration rule, artifacts, and stakeholder report.</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_submission_controls(
    *,
    workflow_options: list[str],
    repository_source_options: dict[str, str],
) -> tuple[str, str, str, str, str, str]:
    with st.container(border=True):
        _render_card_header(
            "Choose review mode",
            "Configure the evidence source first, then run the same three-expert council flow used throughout the lab.",
        )

        _render_field_label("Workflow")
        workflow_label = st.radio(
            "Workflow",
            workflow_options,
            horizontal=True,
            key="workflow_mode",
            label_visibility="collapsed",
        )
        _render_field_help(
            "Repository-only reviews a codebase, Behavior-only reviews a transcript or conversation log, and Hybrid combines both."
        )

        sample_col, sample_transcript_col = st.columns(2)
        with sample_col:
            if st.button("Load sample public repo", use_container_width=True):
                _queue_sample("public_repo")
                st.rerun()
        with sample_transcript_col:
            if st.button("Load sample transcript", use_container_width=True):
                _queue_sample("transcript")
                st.rerun()
        _render_field_help("Use the sample buttons to preview Repository-only or Behavior-only without typing everything from scratch.")

        source_type = "github_url"
        github_url = ""
        local_path = ""
        transcript_text = ""
        source_label = st.session_state.get("repository_source_label", next(iter(repository_source_options)))

        if workflow_label in {"Repository-only", "Hybrid"}:
            _render_field_label("Repository source")
            source_label = st.radio(
                "Repository source",
                list(repository_source_options.keys()),
                horizontal=True,
                key="repository_source_label",
                label_visibility="collapsed",
            )
            source_type = repository_source_options[source_label]
            _render_field_help("Repository-only uses one repository source. Hybrid combines that repository with a transcript.")

            if source_type == "github_url":
                _render_field_label("GitHub URL")
                github_url = st.text_input(
                    "GitHub URL",
                    value=st.session_state.get("github_url_input", DEFAULT_GITHUB_TARGET),
                    placeholder="https://github.com/owner/repository",
                    key="github_url_input",
                    label_visibility="collapsed",
                )
                _render_field_help("Recommended for the smoothest evaluation flow. Paste a public repository link and run the review.")
            else:
                _render_field_label("Local folder path on the backend machine")
                local_path = st.text_input(
                    "Local folder path on the backend machine",
                    value=st.session_state.get("local_path_input", DEFAULT_LOCAL_TARGET),
                    placeholder="/absolute/path/to/repository",
                    key="local_path_input",
                    label_visibility="collapsed",
                )
                _render_field_help("Use this for local debugging or offline review on the same machine as the backend.")

        if workflow_label in {"Behavior-only", "Hybrid"}:
            _render_field_label("Behavior transcript / conversation")
            transcript_text = st.text_area(
                "Behavior transcript / conversation",
                value=st.session_state.get("transcript_input", DEFAULT_TRANSCRIPT),
                height=180,
                key="transcript_input",
                placeholder="User: ...\nAssistant: ...",
                label_visibility="collapsed",
            )
            _render_field_help("First-time tip: use speaker labels when you have them. The text is mapped to the existing `conversation` payload.")
            if workflow_label == "Behavior-only":
                _render_field_help("Leave repository fields blank for Behavior-only; the evaluation will run on the transcript only.")
            else:
                _render_field_help("Hybrid uses both the repository and the transcript in one evaluation.")

        with st.expander("Optional labels", expanded=False):
            _render_field_help("These labels appear in the stakeholder report and saved artifacts.")
            _render_field_label("Display name")
            st.text_input(
                "Display name",
                value=st.session_state.get("target_name_input", "Submitted Repository"),
                key="target_name_input",
                label_visibility="collapsed",
            )
            _render_field_label("Short description")
            st.text_area(
                "Short description",
                value=st.session_state.get("description_input", DEFAULT_DESCRIPTION),
                height=90,
                key="description_input",
                label_visibility="collapsed",
            )

    return workflow_label, source_type, github_url, local_path, transcript_text, source_label


def render_input_page(
    *,
    app_title: str,
    app_subtitle: str,
    workflow_options: list[str],
    repository_source_options: dict[str, str],
    build_payload: Callable[..., dict],
    submit_evaluation: Callable[[str, dict], dict],
) -> None:
    _inject_styles()
    _ensure_state()
    _render_hero(app_title, app_subtitle)
    _render_context_cards()

    left, right = st.columns([1.3, 1])
    with left:
        workflow_label, source_type, github_url, local_path, transcript_text, _ = _render_submission_controls(
            workflow_options=workflow_options,
            repository_source_options=repository_source_options,
        )

    with right:
        with st.container(border=True):
            _render_card_header(
                "What you get",
                "The result view is a report-style dashboard covering all evaluation layers.",
            )
            st.markdown(
                """
                <div class="step-row">
                    <div class="step-num" style="background:linear-gradient(135deg,#2563eb,#1d4ed8);">&#10003;</div>
                    <div class="step-body"><div class="step-title">Submission summary</div>
                    <div class="step-copy">Workflow, target, evidence snapshot.</div></div>
                </div>
                <div class="step-row">
                    <div class="step-num" style="background:linear-gradient(135deg,#2563eb,#1d4ed8);">&#10003;</div>
                    <div class="step-body"><div class="step-title">Expert modules × 3</div>
                    <div class="step-copy">Risk, Red-team, Policy — each with findings and confidence.</div></div>
                </div>
                <div class="step-row">
                    <div class="step-num" style="background:linear-gradient(135deg,#2563eb,#1d4ed8);">&#10003;</div>
                    <div class="step-body"><div class="step-title">Council synthesis</div>
                    <div class="step-copy">Arbitration rule, rationale, recommended actions.</div></div>
                </div>
                <div class="step-row" style="margin-bottom:0;">
                    <div class="step-num" style="background:linear-gradient(135deg,#2563eb,#1d4ed8);">&#10003;</div>
                    <div class="step-body"><div class="step-title">Artifacts & raw output</div>
                    <div class="step-copy">Downloadable report and archive JSON for audit trail.</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    target_name = st.session_state.get("target_name_input", "Submitted Repository")
    description = st.session_state.get("description_input", DEFAULT_DESCRIPTION)
    api_base = st.session_state.get("api_base_input", DEFAULT_API_BASE)
    target_endpoint = st.session_state.get("target_endpoint_input", "")
    target_model = st.session_state.get("target_model_input", "")

    with st.container(border=True):
        _render_card_header(
            "Run evaluation",
            "Submit to the backend. The three-expert council evaluates in sequence, then the council synthesizes a final decision.",
        )
        submitted = st.button("&#9658;  Run Evaluation", use_container_width=True)

    if submitted:
        if workflow_label in {"Repository-only", "Hybrid"} and source_type == "local_path" and not local_path.strip():
            st.warning("Please provide a local path.")
            return
        if workflow_label in {"Repository-only", "Hybrid"} and source_type == "github_url" and not github_url.strip():
            st.warning("Please provide a GitHub URL.")
            return
        if workflow_label in {"Behavior-only", "Hybrid"} and not transcript_text.strip():
            st.warning("Please provide a behavior transcript or conversation log.")
            return

        st.session_state.submitted_workflow_mode = workflow_label
        payload = build_payload(
            workflow_label,
            source_type,
            github_url,
            local_path,
            target_name,
            description,
            transcript_text,
            target_endpoint,
            target_model,
        )
        with st.spinner("Running expert evaluation..."):
            try:
                st.session_state.evaluation_result = submit_evaluation(api_base, payload)
                st.session_state.current_page = "result"
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(f"Backend returned {exc.response.status_code}: {exc.response.text}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Evaluation failed: {exc}")
