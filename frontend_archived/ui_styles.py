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
        /* ── Base ───────────────────────────────────────────── */
        .stApp {
            background:
                radial-gradient(ellipse at top right, rgba(241, 90, 36, 0.08), transparent 38%),
                linear-gradient(180deg, #f5f1e8 0%, #f0ece2 100%);
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

        /* ── Shared card shell ──────────────────────────────── */
        .hero-card,
        .section-card,
        .sidebar-card,
        .step-card,
        .module-card,
        .metric-card,
        .trace-card,
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 252, 247, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 22px;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 1.1rem 1.2rem !important;
            margin-bottom: 1rem !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] > div {
            background: transparent !important;
            border: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            padding: 0 !important;
        }

        /* ── Hero card ──────────────────────────────────────── */
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

        /* ── Hero typography ────────────────────────────────── */
        .hero-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: #f15a24;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.7rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
        }

        .hero-eyebrow::before {
            content: '';
            display: inline-block;
            width: 18px;
            height: 2px;
            background: linear-gradient(90deg, #f15a24, #ea580c);
            border-radius: 2px;
        }

        .hero-title {
            font-size: 2.25rem;
            line-height: 1.08;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.4rem;
            letter-spacing: -0.025em;
        }

        .hero-copy {
            color: #475569;
            font-size: 1rem;
            line-height: 1.65;
            max-width: 60ch;
        }

        .body-copy {
            color: #475569;
            line-height: 1.65;
            margin-top: 0.3rem;
        }

        .hero-pill-row {
            margin-top: 1.1rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
        }

        .hero-list {
            margin: 0.7rem 0 0 0;
            padding-left: 1.15rem;
            color: #334155;
            line-height: 1.65;
        }

        /* ── Metric cards ───────────────────────────────────── */
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

        /* ── Tone variants ──────────────────────────────────── */
        .tone-red    { background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%); border-left-color: #e11d48; }
        .tone-amber  { background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%); border-left-color: #ea580c; }
        .tone-yellow { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-left-color: #d97706; }
        .tone-green  { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-left-color: #16a34a; }
        .tone-blue   { background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left-color: #2563eb; }

        /* ── Risk labels ────────────────────────────────────── */
        .risk-high   { color: #be123c; font-weight: 700; }
        .risk-medium { color: #b45309; font-weight: 700; }
        .risk-low    { color: #15803d; font-weight: 700; }

        /* ── Status badges ──────────────────────────────────── */
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.28rem 0.7rem;
            border-radius: 999px;
            font-size: 0.73rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .badge-reject  { background: #fff1f2; color: #be123c; border: 1.5px solid #fecdd3; }
        .badge-review  { background: #fffbeb; color: #92400e; border: 1.5px solid #fde68a; }
        .badge-approve { background: #f0fdf4; color: #166534; border: 1.5px solid #bbf7d0; }
        .badge-info    { background: #eff6ff; color: #1e40af; border: 1.5px solid #bfdbfe; }
        .badge-neutral { background: #f8fafc; color: #475569; border: 1.5px solid #e2e8f0; }

        /* ── Pills ──────────────────────────────────────────── */
        .pill {
            display: inline-flex;
            align-items: center;
            padding: 0.3rem 0.75rem;
            border-radius: 999px;
            background: rgba(241, 90, 36, 0.08);
            color: #c2410c;
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid rgba(241, 90, 36, 0.16);
        }

        .pill-neutral {
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #e2e8f0;
        }

        .pill-green {
            background: rgba(22, 163, 74, 0.07);
            color: #166534;
            border: 1px solid rgba(22, 163, 74, 0.18);
        }

        .pill-blue {
            background: rgba(37, 99, 235, 0.07);
            color: #1d4ed8;
            border: 1px solid rgba(37, 99, 235, 0.18);
        }

        .muted { color: #64748b; }

        /* ── Sidebar ────────────────────────────────────────── */
        .sidebar-title {
            font-size: 1.1rem;
            font-weight: 800;
            color: #0f172a;
        }

        .sidebar-eyebrow {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #f15a24;
            margin-bottom: 0.4rem;
        }

        /* ── Card titles ────────────────────────────────────── */
        .card-flush { margin-bottom: 0; }

        .card-title {
            margin-top: 0;
            margin-bottom: 0.5rem;
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 800;
            letter-spacing: -0.015em;
        }

        .field-label {
            color: #374151;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin: 0.2rem 0 0.35rem 0;
        }

        .field-help {
            color: #64748b;
            font-size: 0.88rem;
            line-height: 1.55;
            margin: 0.2rem 0 0.85rem 0;
        }

        .card-copy {
            color: #475569;
            line-height: 1.6;
            margin-top: 0.45rem;
        }

        .card-copy strong {
            color: #0f172a;
        }

        .card-list {
            margin: 0.35rem 0 0.9rem 1.1rem;
            padding: 0;
            color: #475569;
            line-height: 1.55;
        }

        .card-list li {
            margin-bottom: 0.35rem;
        }

        .section-card code,
        .module-card code {
            background: rgba(226, 232, 240, 0.7);
            border-radius: 8px;
            padding: 0.12rem 0.35rem;
            color: #0f172a;
            font-size: 0.84em;
        }

        /* ── Code / trace ───────────────────────────────────── */
        .trace-card pre { white-space: pre-wrap; }

        /* ── Radio / expander text ──────────────────────────── */
        .stRadio [data-baseweb="radio"] [data-testid="stMarkdownContainer"] p,
        .stExpander summary [data-testid="stMarkdownContainer"] p {
            color: #0f172a !important;
        }

        /* ── Text inputs ────────────────────────────────────── */
        .stTextInput input,
        .stTextArea textarea,
        section[data-testid="stSidebar"] .stTextInput input,
        section[data-testid="stSidebar"] .stTextArea textarea {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder,
        section[data-testid="stSidebar"] .stTextInput input::placeholder,
        section[data-testid="stSidebar"] .stTextArea textarea::placeholder {
            color: rgba(255, 255, 255, 0.5) !important;
            -webkit-text-fill-color: rgba(255, 255, 255, 0.5) !important;
            opacity: 1;
        }

        /* ── Buttons ────────────────────────────────────────── */
        .stButton > button {
            background: linear-gradient(135deg, #f15a24 0%, #dc4b10 100%);
            color: white !important;
            border-radius: 12px;
            border: none;
            padding: 0.72rem 1.1rem;
            font-weight: 700;
            font-size: 0.88rem;
            letter-spacing: 0.015em;
            box-shadow: 0 2px 6px rgba(241, 90, 36, 0.3), 0 1px 2px rgba(241, 90, 36, 0.2);
            transition: filter 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
        }

        .stButton > button:hover {
            color: white !important;
            filter: brightness(1.07);
            box-shadow: 0 4px 14px rgba(241, 90, 36, 0.38), 0 2px 4px rgba(241, 90, 36, 0.2);
            transform: translateY(-1px);
        }

        .stButton > button:active {
            transform: translateY(0);
            filter: brightness(0.97);
        }

        /* ── Layout helpers ─────────────────────────────────── */
        .dashboard-stack { display: grid; gap: 1rem; }

        .pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.9rem;
        }

        .action-note {
            color: #475569;
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .empty-state    { text-align: center; padding: 2rem; }
        .empty-title    { font-size: 1.3rem; font-weight: 800; color: #0f172a; margin-bottom: 0.4rem; }
        .empty-copy     { color: #64748b; line-height: 1.65; margin-bottom: 1rem; }

        /* ── KV grid ────────────────────────────────────────── */
        .kv-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.65rem;
        }

        .kv-item {
            background: rgba(248, 250, 252, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 16px;
            padding: 0.85rem 0.95rem;
        }

        .kv-label {
            font-size: 0.7rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            margin-bottom: 0.3rem;
        }

        .kv-value {
            font-size: 0.95rem;
            color: #0f172a;
            line-height: 1.4;
            font-weight: 600;
        }

        .split-grid {
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 1rem;
        }

        .workflow-highlight {
            margin-top: 0.45rem;
            font-weight: 700;
            color: #0f172a;
        }

        /* ── Step numbers ───────────────────────────────────── */
        .step-row {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            margin-bottom: 0.7rem;
        }

        .step-num {
            flex-shrink: 0;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: linear-gradient(135deg, #f15a24, #dc4b10);
            color: white;
            font-size: 0.7rem;
            font-weight: 800;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 0.08rem;
            box-shadow: 0 2px 6px rgba(241, 90, 36, 0.32);
        }

        .step-body { flex: 1; }
        .step-title { font-weight: 700; color: #0f172a; font-size: 0.9rem; line-height: 1.3; }
        .step-copy  { color: #64748b; font-size: 0.83rem; line-height: 1.45; margin-top: 0.15rem; }

        /* ── Divider ────────────────────────────────────────── */
        .section-divider {
            border: none;
            border-top: 1px solid rgba(148, 163, 184, 0.18);
            margin: 0.75rem 0;
        }

        /* ── Download button ────────────────────────────────── */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #f15a24 0%, #dc4b10 100%) !important;
            color: white !important;
            border-radius: 12px !important;
            border: none !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 6px rgba(241, 90, 36, 0.28) !important;
        }

        .stDownloadButton > button:hover {
            filter: brightness(1.07) !important;
            transform: translateY(-1px) !important;
        }

        /* ── Responsive ─────────────────────────────────────── */
        @media (max-width: 900px) {
            .kv-grid, .split-grid { grid-template-columns: 1fr; }
            .hero-title { font-size: 1.75rem; }
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
