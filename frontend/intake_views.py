from __future__ import annotations

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


def _render_card_header(title: str, copy: str | None = None) -> None:
    st.markdown(f'<h3 class="card-title">{title}</h3>', unsafe_allow_html=True)
    if copy:
        st.markdown(f'<p class="body-copy">{copy}</p>', unsafe_allow_html=True)


def _render_field_label(label: str) -> None:
    st.markdown(f'<div class="field-label">{label}</div>', unsafe_allow_html=True)


def _render_field_help(copy: str) -> None:
    st.markdown(f'<p class="field-help">{copy}</p>', unsafe_allow_html=True)


def _render_card(title: str, lines: list[str]) -> None:
    st.markdown("<div class='sidebar-card'>", unsafe_allow_html=True)
    st.markdown(f"**{title}**")
    for line in lines:
        st.markdown(f"- {line}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar(app_title: str, app_subtitle: str) -> None:
    _inject_styles()
    _ensure_state()

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-card">
                <div class="hero-eyebrow">Stakeholder intake</div>
                <div class="sidebar-title">{app_title}</div>
                <div class="body-copy">{app_subtitle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Navigation**")
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

        st.markdown("**Advanced settings**")
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

        current_workflow = st.session_state.get("workflow_mode", "Repository-only")
        current_source = st.session_state.get("repository_source_label", "Public GitHub repository (recommended)")
        _render_card(
            "Current state",
            [
                f"Workflow: {current_workflow}",
                f"Repository source: {current_source if current_workflow != 'Behavior-only' else 'Not used'}",
                f"Page: {st.session_state.get('current_page', 'input')}",
            ],
        )

        _render_card(
            "Quick notes",
            [
                "Repository-only, Behavior-only, and Hybrid all stay on the same intake path.",
                "Sample buttons preload state and keep the current form shape intact.",
                "Advanced settings are stored in session state and reused on submit.",
            ],
        )


def _render_hero(app_title: str, app_subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-eyebrow">Review intake</div>
            <div class="hero-title">{app_title}</div>
            <div class="hero-copy">{app_subtitle}</div>
            <div class="hero-pill-row">
                <span class="pill">Repository-only</span>
                <span class="pill">Behavior-only</span>
                <span class="pill">Hybrid</span>
                <span class="pill">three experts + council</span>
                <span class="pill">stakeholder-ready report</span>
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
                <p class="body-copy">Submit a repository, a transcript, or both. The intake flow preserves the same evaluation logic while letting stakeholders choose Repository-only, Behavior-only, or Hybrid review.</p>
                <p class="body-copy"><strong>Repository-only:</strong> public GitHub repository or local folder on the backend machine.</p>
                <p class="body-copy"><strong>Behavior-only:</strong> transcript or conversation log mapped into the existing `conversation` payload.</p>
                <p class="body-copy"><strong>Hybrid:</strong> repository evidence and transcript evidence in one council evaluation.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="section-card">
                <h3 class="card-title">Workflow</h3>
                <p class="body-copy">Choose the review mode, fill in the relevant submission details, and run the evaluation. The result page then shows expert modules, council synthesis, artifacts, and raw API output.</p>
                <p class="body-copy"><strong>Suggested workflow:</strong></p>
                <p class="body-copy">1. Choose Repository-only, Behavior-only, or Hybrid.</p>
                <p class="body-copy">2. Add a repository, a transcript, or both.</p>
                <p class="body-copy">3. Review the expert findings, arbitration rule, and stakeholder report.</p>
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
                "Result page structure",
                "The result view opens as a report-style dashboard with the same section order used by the actual evaluation output.",
            )
            st.markdown("- Submission summary and evidence snapshot")
            st.markdown("- Repository evidence and behavior evidence when available")
            st.markdown("- Expert modules followed by council synthesis")
            st.markdown("- Artifacts and raw API response for traceability")

    target_name = st.session_state.get("target_name_input", "Submitted Repository")
    description = st.session_state.get("description_input", DEFAULT_DESCRIPTION)
    api_base = st.session_state.get("api_base_input", DEFAULT_API_BASE)
    target_endpoint = st.session_state.get("target_endpoint_input", "")
    target_model = st.session_state.get("target_model_input", "")

    with st.container(border=True):
        _render_card_header(
            "Run evaluation",
            "Submit the intake package to the backend and open the council dashboard when the evaluation completes.",
        )
        submitted = st.button("Run evaluation", use_container_width=True)

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
