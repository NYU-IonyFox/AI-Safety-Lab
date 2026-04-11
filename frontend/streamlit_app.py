from __future__ import annotations

import httpx
import streamlit as st

from intake_views import render_input_page, render_sidebar
from result_views import render_result_page
from ui_styles import inject_styles

APP_TITLE = "AI Safety Lab"
APP_SUBTITLE = "A stakeholder-facing AI safety evaluation workspace for Repository-only, Behavior-only, and Hybrid reviews."
DEFAULT_API_BASE = "http://127.0.0.1:8081"
DEFAULT_GITHUB_TARGET = ""
DEFAULT_LOCAL_TARGET = ""
DEFAULT_DESCRIPTION = "Repository submission for AI safety review."
DEFAULT_TRANSCRIPT = ""

WORKFLOW_OPTIONS = ["Repository-only", "Behavior-only", "Hybrid"]
REPOSITORY_SOURCE_OPTIONS = {
    "Public GitHub repository (recommended)": "github_url",
    "Local folder on this machine": "local_path",
}

st.set_page_config(page_title=APP_TITLE, page_icon="🛡️", layout="wide")


def ensure_state() -> None:
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


def parse_transcript(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    turns: list[dict[str, str]] = []
    current_role = "user"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            turns.append({"role": current_role, "content": content})
        buffer = []

    prefix_map = {
        "system:": "system",
        "user:": "user",
        "human:": "user",
        "assistant:": "assistant",
        "agent:": "assistant",
        "model:": "assistant",
    }

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            if buffer:
                buffer.append("")
            continue
        lower = stripped.lower()
        matched_role = None
        matched_prefix = ""
        for prefix, role in prefix_map.items():
            if lower.startswith(prefix):
                matched_role = role
                matched_prefix = prefix
                break
        if matched_role is not None:
            flush()
            current_role = matched_role
            remainder = stripped[len(matched_prefix) :].strip()
            buffer = [remainder] if remainder else []
            continue
        buffer.append(stripped)

    flush()
    if not turns and text.strip():
        return [{"role": "user", "content": text.strip()}]
    return turns


def build_payload(
    workflow_mode: str,
    source_type: str,
    github_url: str,
    local_path: str,
    target_name: str,
    description: str,
    transcript_text: str,
    target_endpoint: str,
    target_model: str,
) -> dict:
    conversation = parse_transcript(transcript_text)
    payload = {
        "context": {
            "agent_name": target_name or ("Behavior Review" if workflow_mode == "Behavior-only" else "Submitted Submission"),
            "description": description,
            "domain": "Other",
            "capabilities": [],
            "high_autonomy": False,
        },
        "selected_policies": ["eu_ai_act", "us_nist", "iso", "unesco"],
        "conversation": conversation,
        "metadata": {},
    }
    if workflow_mode != "Behavior-only":
        payload["submission"] = {
            "source_type": source_type,
            "github_url": github_url.strip(),
            "local_path": local_path.strip(),
            "target_name": target_name.strip(),
            "description": description.strip(),
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


def main() -> None:
    inject_styles()
    ensure_state()
    render_sidebar(APP_TITLE, APP_SUBTITLE)

    if st.session_state.get("current_page") == "result":
        render_result_page(st.session_state.get("evaluation_result"))
        return

    render_input_page(
        app_title=APP_TITLE,
        app_subtitle=APP_SUBTITLE,
        workflow_options=WORKFLOW_OPTIONS,
        repository_source_options=REPOSITORY_SOURCE_OPTIONS,
        build_payload=build_payload,
        submit_evaluation=submit_evaluation,
    )


if __name__ == "__main__":
    main()
