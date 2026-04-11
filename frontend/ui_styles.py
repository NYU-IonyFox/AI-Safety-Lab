from __future__ import annotations

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

        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }

        .hero-card,
        .section-card,
        .sidebar-card,
        .step-card,
        .module-card,
        .metric-card,
        .trace-card {
            background: rgba(255, 252, 247, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 22px;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
        }

        .hero-card {
            padding: 1.4rem 1.5rem;
            margin-bottom: 1rem;
        }

        .section-card,
        .sidebar-card,
        .step-card,
        .module-card,
        .trace-card {
            padding: 1.1rem 1.2rem;
            margin-bottom: 1rem;
        }

        .hero-eyebrow {
            color: #b45309;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
        }

        .hero-title {
            font-size: 2.1rem;
            line-height: 1.1;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.35rem;
        }

        .hero-copy {
            color: #475569;
            font-size: 1rem;
            line-height: 1.6;
        }

        .body-copy {
            color: #475569;
            line-height: 1.6;
            margin-top: 0.35rem;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: 1.35fr 0.9fr;
            gap: 1rem;
            align-items: start;
        }

        .hero-pill-row {
            margin-top: 0.8rem;
        }

        .hero-list {
            margin: 0.7rem 0 0 0;
            padding-left: 1.15rem;
            color: #334155;
            line-height: 1.6;
        }

        .metric-card {
            padding: 1.15rem 1.2rem;
            min-height: 152px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            border-left: 8px solid transparent;
        }

        .metric-label {
            color: #64748b;
            font-size: 0.86rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-bottom: 0.55rem;
        }

        .metric-value {
            font-size: 1.7rem;
            line-height: 1.15;
            font-weight: 800;
            color: #0f172a;
        }

        .metric-copy {
            margin-top: 0.45rem;
            font-size: 0.95rem;
            color: #475569;
            line-height: 1.45;
        }

        .tone-red {
            background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%);
            border-left-color: #e11d48;
        }

        .tone-amber {
            background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
            border-left-color: #ea580c;
        }

        .tone-yellow {
            background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
            border-left-color: #d97706;
        }

        .tone-green {
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border-left-color: #16a34a;
        }

        .tone-blue {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-left-color: #2563eb;
        }

        .risk-high {
            color: #be123c;
            font-weight: 700;
        }

        .risk-medium {
            color: #b45309;
            font-weight: 700;
        }

        .risk-low {
            color: #15803d;
            font-weight: 700;
        }

        .pill {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: #e2e8f0;
            color: #334155;
            font-size: 0.82rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }

        .muted {
            color: #64748b;
        }

        .sidebar-title {
            font-size: 1.2rem;
            font-weight: 800;
            color: #0f172a;
        }

        .card-flush {
            margin-bottom: 0;
        }

        .workflow-highlight {
            margin-top: 0.45rem;
            font-weight: 700;
            color: #0f172a;
        }

        .card-title {
            margin-top: 0;
            margin-bottom: 0.45rem;
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 800;
        }

        .trace-card pre {
            white-space: pre-wrap;
        }

        .stButton > button {
            background: linear-gradient(135deg, #f15a24 0%, #ea580c 100%);
            color: white;
            border-radius: 12px;
            border: none;
            padding: 0.75rem 1rem;
            font-weight: 700;
        }

        .stButton > button:hover {
            color: white;
            filter: brightness(0.97);
        }

        .dashboard-stack {
            display: grid;
            gap: 1rem;
        }

        .pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-top: 0.8rem;
        }

        .action-note {
            color: #475569;
            font-size: 0.95rem;
            line-height: 1.45;
        }

        .empty-state {
            text-align: center;
        }

        .empty-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.35rem;
        }

        .empty-copy {
            color: #475569;
            line-height: 1.6;
            margin-bottom: 0.9rem;
        }

        .kv-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.7rem;
        }

        .kv-item {
            background: #fffaf4;
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 18px;
            padding: 0.85rem 0.9rem;
        }

        .kv-label {
            font-size: 0.78rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.25rem;
        }

        .kv-value {
            font-size: 0.95rem;
            color: #0f172a;
            line-height: 1.45;
        }

        .split-grid {
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 1rem;
        }

        @media (max-width: 900px) {
            .hero-grid,
            .kv-grid,
            .split-grid {
                grid-template-columns: 1fr;
            }

            .hero-title {
                font-size: 1.7rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, tone_class: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card {_escape(tone_class)}">
            <div class="metric-label">{_escape(label)}</div>
            <div class="metric-value">{_escape(value)}</div>
            <div class="metric-copy">{_escape(copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tone_for_decision(decision: str) -> str:
    value = str(decision).strip().lower()
    if any(term in value for term in ("reject", "not approved", "block", "flag", "deny", "critical fail")):
        return "tone-red"
    if any(term in value for term in ("review", "human review", "needs review", "escalate", "uncertain")):
        return "tone-yellow"
    if any(term in value for term in ("approve", "approved", "clear", "pass", "safe")):
        return "tone-green"
    return "tone-blue"


def tone_for_risk(risk_tier: str) -> str:
    value = str(risk_tier).strip().lower()
    if any(term in value for term in ("critical", "severe", "high", "unacceptable", "tier_4", "tier_3")):
        return "tone-red"
    if any(term in value for term in ("medium", "moderate", "limited", "review", "tier_2")):
        return "tone-amber"
    if any(term in value for term in ("low", "minimal", "acceptable", "safe", "tier_1")):
        return "tone-green"
    return "tone-blue"


def risk_class(risk_tier: str) -> str:
    value = str(risk_tier).strip().lower()
    if any(term in value for term in ("critical", "severe", "high", "unacceptable", "tier_4", "tier_3")):
        return "risk-high"
    if any(term in value for term in ("medium", "moderate", "limited", "review", "tier_2")):
        return "risk-medium"
    return "risk-low"
