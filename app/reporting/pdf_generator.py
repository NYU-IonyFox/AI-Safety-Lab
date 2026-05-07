from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.safe_schemas import SAFEEvaluationResponse

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
_DARK_BG = HexColor("#44403C")
_RULE_REF_BG = HexColor("#F5F0EB")

_COVER_VERDICT_COLORS: dict[str, str] = {
    "REJECT":  "#F2A8A8",
    "HOLD":    "#FDE68A",
    "APPROVE": "#BBF7D0",
}
_COVER_VERDICT_BORDER: dict[str, str] = {
    "REJECT":  "#E88080",
    "HOLD":    "#D4A820",
    "APPROVE": "#4A9B6F",
}
_INNER_VERDICT_TEXT: dict[str, str] = {
    "REJECT":  "#A32D2D",
    "HOLD":    "#854F0B",
    "APPROVE": "#3B6D11",
}
_INNER_VERDICT_BG: dict[str, str] = {
    "REJECT":  "#FCEBEB",
    "HOLD":    "#FAEEDA",
    "APPROVE": "#EAF3DE",
}
_EXPERT_COLORS: dict[str, str] = {
    "expert_adversarial_security": "#3D6070",
    "expert_content_safety":       "#4A4880",
    "expert_governance_un":        "#634078",
}
_EXPERT_DISPLAY: dict[str, str] = {
    "expert_adversarial_security": "Expert 1 — Adversarial Security",
    "expert_content_safety":       "Expert 2 — Content Safety",
    "expert_governance_un":        "Expert 3 — Governance & UN",
}
_SEV_BG: dict[str, str] = {
    "HIGH":   "#FCEBEB",
    "MEDIUM": "#FAEEDA",
    "LOW":    "#EAF3DE",
}
_SEV_TEXT: dict[str, str] = {
    "HIGH":   "#A32D2D",
    "MEDIUM": "#854F0B",
    "LOW":    "#3B6D11",
}
_VERDICT_BADGE: dict[str, str] = {
    "REJECT":  "Do not deploy into UNICC systems",
    "HOLD":    "Human review required",
    "APPROVE": "Cleared for UNICC deployment",
}

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _ps(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


# ---------------------------------------------------------------------------
# Structured filename
# ---------------------------------------------------------------------------
def make_filename(response: SAFEEvaluationResponse, ext: str) -> str:
    """Return a structured filename: {target}_{verdict}_{YYYYMMDD}.{ext}"""
    target = response.submission_context.get("target_name", "unknown")
    target = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(target).replace(" ", "_"))[:32]
    date_str = (response.timestamp or "")[:10].replace("-", "")
    return f"{target}_{response.verdict}_{date_str}.{ext}"


# ---------------------------------------------------------------------------
# Cover page — canvas callback: dark bg + SAFE header + logos + color bar
# ---------------------------------------------------------------------------
def _cover_canvas(
    canvas, doc, verdict: str, response: SAFEEvaluationResponse
) -> None:
    if doc.page != 1:
        return
    canvas.saveState()
    w, h = A4

    # Dark background
    canvas.setFillColor(_DARK_BG)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)

    # SAFE wordmark — top-left
    canvas.setFillColor(HexColor("#FAFAF8"))
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(36, h - 54, "SAFE")

    # Subtitle
    canvas.setFillColor(HexColor("#A8A29E"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(36, h - 68, "Safety Assurance Framework for Evaluation")

    # Logo images — best-effort, skip silently on any error
    try:
        unicc_path = str(_ASSETS_DIR / "透明底白色UNICC.png")
        nyu_path = str(_ASSETS_DIR / "透明底白色NYU.png")
        logo_y = h - 78
        if os.path.exists(unicc_path):
            canvas.drawImage(
                unicc_path, w - 130, logo_y,
                width=54, height=28,
                preserveAspectRatio=True, mask="auto",
            )
        if os.path.exists(nyu_path):
            canvas.drawImage(
                nyu_path, w - 72, logo_y,
                width=48, height=28,
                preserveAspectRatio=True, mask="auto",
            )
    except Exception:
        pass

    # Bottom color bar (20pt high)
    vcolor = HexColor(_COVER_VERDICT_COLORS.get(verdict, "#FDE68A"))
    canvas.setFillColor(vcolor)
    canvas.rect(0, 0, w, 20, fill=1, stroke=0)

    # Metadata text in bar — right-aligned, white, 7pt
    canvas.setFillColor(white)
    canvas.setFont("Helvetica", 7)
    ts = (response.timestamp or "")[:19].replace("T", " ")
    meta = (
        f"Evaluation ID: {response.evaluation_id}"
        f"  ·  {ts}"
        f"  ·  SAFE v{response.safe_version}"
    )
    canvas.drawRightString(w - 16, 6, meta)

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Cover page — Platypus body (center section)
# ---------------------------------------------------------------------------
def _cover_page(response: SAFEEvaluationResponse) -> list:
    verdict = response.verdict
    vcolor = HexColor(_COVER_VERDICT_COLORS.get(verdict, "#FDE68A"))
    vborder = HexColor(_COVER_VERDICT_BORDER.get(verdict, "#D4A820"))
    badge_text = _VERDICT_BADGE.get(verdict, "")
    target = response.submission_context.get("target_name", "Unknown Target")
    rule_text = response.primary_reason.get("decision_rule_triggered",
                response.primary_reason.get("rule", "—"))

    sty_eyebrow = _ps("CoverEyebrow", fontName="Helvetica", fontSize=9,
                      textColor=HexColor("#A8A29E"), alignment=TA_LEFT, spaceAfter=8)
    sty_target = _ps("CoverTarget", fontName="Helvetica-Bold", fontSize=22,
                     textColor=HexColor("#FAFAF8"), alignment=TA_LEFT, spaceAfter=20,
                     leading=28)
    sty_verdict = _ps("CoverVerdict", fontName="Helvetica-Bold", fontSize=72,
                      textColor=vcolor, alignment=TA_LEFT, spaceAfter=10, leading=80)
    sty_badge = _ps("CoverBadge", fontName="Helvetica", fontSize=10,
                    textColor=vcolor, alignment=TA_LEFT, spaceAfter=16)
    sty_rule = _ps("CoverRule", fontName="Helvetica", fontSize=10,
                   textColor=HexColor("#C8C0B8"), alignment=TA_LEFT,
                   spaceAfter=4, leading=15)

    elements: list = []
    # Spacer to push content below the canvas-drawn SAFE header (~80pt)
    elements.append(Spacer(1, 3.2 * cm))

    elements.append(Paragraph("Evaluation Report", sty_eyebrow))
    elements.append(Paragraph(_esc(str(target)), sty_target))
    elements.append(Paragraph(_esc(verdict), sty_verdict))
    elements.append(Paragraph(_esc(badge_text), sty_badge))

    # Primary reason block with left border
    rule_block = Table(
        [[Paragraph(_esc(str(rule_text)), sty_rule)]],
        colWidths=[14 * cm],
    )
    rule_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#141210")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBEFORE", (0, 0), (0, -1), 2, vborder),
    ]))
    elements.append(rule_block)
    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Page 2 — Executive Summary
# ---------------------------------------------------------------------------
def _exec_summary_page(response: SAFEEvaluationResponse) -> list:
    verdict = response.verdict
    vtext = HexColor(_INNER_VERDICT_TEXT.get(verdict, "#854F0B"))
    vbg = HexColor(_INNER_VERDICT_BG.get(verdict, "#FAEEDA"))
    badge_text = _VERDICT_BADGE.get(verdict, "")
    rule_text = response.primary_reason.get("decision_rule_triggered",
                response.primary_reason.get("rule", "—"))
    sc = response.submission_context or {}

    sty_h1 = _ps("H1", fontName="Helvetica-Bold", fontSize=14,
                 textColor=_DARK_BG, spaceBefore=4, spaceAfter=8)
    sty_verdict_lg = _ps("VerdictLg", fontName="Helvetica-Bold", fontSize=36,
                         textColor=vtext, alignment=TA_LEFT, spaceAfter=4, leading=42)
    sty_badge = _ps("Badge2", fontName="Helvetica-Bold", fontSize=9,
                    textColor=vtext, spaceAfter=8)
    sty_rule = _ps("Rule2", fontName="Helvetica", fontSize=9,
                   textColor=HexColor("#57534E"), spaceAfter=4, leading=14)
    sty_meta = _ps("Meta2", fontName="Helvetica", fontSize=8,
                   textColor=HexColor("#A8A29E"), spaceAfter=8, leading=12)
    sty_h2 = _ps("H2", fontName="Helvetica-Bold", fontSize=11,
                 textColor=_DARK_BG, spaceBefore=12, spaceAfter=6)
    sty_body = _ps("Body2", fontName="Helvetica", fontSize=9,
                   textColor=black, leading=14, spaceAfter=4)
    sty_rec = _ps("Rec2", fontName="Helvetica", fontSize=9,
                  textColor=HexColor("#1C1917"), leading=14, spaceAfter=3)
    sty_rec_num = _ps("RecNum2", fontName="Helvetica-Bold", fontSize=9,
                      textColor=_DARK_BG, spaceAfter=3)

    elements: list = []
    elements.append(Paragraph("Executive Summary", sty_h1))

    # Verdict + badge side by side
    verdict_row = Table(
        [[Paragraph(_esc(verdict), sty_verdict_lg),
          Paragraph(_esc(badge_text), sty_badge)]],
        colWidths=[5.5 * cm, 10.5 * cm],
    )
    verdict_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(verdict_row)

    # Rule reference block
    rule_block = Table(
        [[Paragraph(_esc(str(rule_text)), sty_rule)]],
        colWidths=[16 * cm],
    )
    rule_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _RULE_REF_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBEFORE", (0, 0), (0, -1), 2, _DARK_BG),
    ]))
    elements.append(rule_block)
    elements.append(Spacer(1, 0.15 * cm))

    # Metadata row
    input_type = sc.get("source_type", sc.get("input_type", "—"))
    mode_str = sc.get("mode", "LLM API")
    ts = (response.timestamp or "")[:19].replace("T", " ")
    meta_str = (
        f"Input type: {input_type}  ·  Mode: {mode_str}"
        f"  ·  ID: {response.evaluation_id}  ·  {ts}"
    )
    elements.append(Paragraph(_esc(meta_str), sty_meta))
    elements.append(Spacer(1, 0.3 * cm))

    # Expert risk summary
    expert_summary = response.primary_reason.get("expert_summary", {})
    if expert_summary:
        elements.append(Paragraph("Expert Risk Summary", sty_h2))
        rows = [["Expert", "Overall Risk"]]
        for slot, level in expert_summary.items():
            label = _EXPERT_DISPLAY.get(slot, slot)
            rows.append([_esc(str(label)), _esc(str(level))])
        t = Table(rows, colWidths=[11 * cm, 5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _RULE_REF_BG),
            ("TEXTCOLOR",  (0, 0), (-1, 0), _DARK_BG),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#FAFAF9")]),
            ("GRID",       (0, 0), (-1, -1), 0.3, HexColor("#E7E5E4")),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.4 * cm))

    # Additional findings
    if response.additional_findings:
        elements.append(Paragraph("Additional Findings", sty_h2))
        for finding in response.additional_findings:
            elements.append(Paragraph(_esc(f"• {finding}"), sty_body))
        elements.append(Spacer(1, 0.2 * cm))

    # Recommendations
    elements.append(Paragraph("Recommendations", sty_h2))
    if response.recommendations:
        for i, rec in enumerate(response.recommendations, 1):
            text = rec.get("text", "")
            src = rec.get("source_expert", "")
            dim = rec.get("source_dimension", "")
            src_label = f"— {src}" + (f" · {dim}" if dim else "")
            rec_body = _esc(str(text))
            if src:
                rec_body += (
                    f'<br/><font color="#A8A29E" size="8">'
                    f'<i>{_esc(src_label)}</i></font>'
                )
            rec_row = Table(
                [[Paragraph(f"{i}.", sty_rec_num),
                  Paragraph(rec_body, sty_rec)]],
                colWidths=[0.7 * cm, 15.3 * cm],
            )
            rec_row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(rec_row)
    else:
        elements.append(Paragraph(
            "No specific remediation recommendations generated.", sty_body))

    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Page 3 — Expert Council Findings
# ---------------------------------------------------------------------------
def _expert_findings_page(response: SAFEEvaluationResponse) -> list:
    sty_h1 = _ps("H1F", fontName="Helvetica-Bold", fontSize=14,
                 textColor=_DARK_BG, spaceBefore=4, spaceAfter=10)
    sty_h2 = _ps("H2F", fontName="Helvetica-Bold", fontSize=10,
                 textColor=white, spaceAfter=0)
    sty_overall = _ps("OverallF", fontName="Helvetica-Bold", fontSize=9,
                      textColor=white, spaceAfter=0)
    sty_none = _ps("NoneF", fontName="Helvetica", fontSize=9,
                   textColor=HexColor("#A8A29E"), spaceAfter=6)
    sty_reason = _ps("ReasonF", fontName="Helvetica", fontSize=8,
                     textColor=HexColor("#57534E"), leading=12,
                     spaceAfter=3, leftIndent=10)
    sty_dim_name = _ps("DimName", fontName="Helvetica", fontSize=9,
                       textColor=_DARK_BG, leading=13)
    sty_dim_lvl = _ps("DimLvl", fontName="Helvetica-Bold", fontSize=8,
                      textColor=_DARK_BG, alignment=TA_CENTER)
    sty_dim_anchor = _ps("DimAnchor", fontName="Helvetica", fontSize=7,
                         textColor=HexColor("#A8A29E"), leading=10)

    elements: list = []
    elements.append(Paragraph("Expert Council Findings", sty_h1))

    for expert in response.experts:
        expert_color = HexColor(_EXPERT_COLORS.get(expert.id, "#44403C"))
        label = _EXPERT_DISPLAY.get(expert.id, expert.id)

        # Expert header bar
        header = Table(
            [[Paragraph(_esc(label), sty_h2),
              Paragraph(_esc(f"Overall: {expert.overall}"), sty_overall)]],
            colWidths=[12 * cm, 4 * cm],
        )
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), expert_color),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(header)

        if not expert.triggered_dimensions:
            elements.append(Paragraph(
                "No dimensions triggered — all within acceptable range.",
                sty_none,
            ))
            elements.append(Spacer(1, 0.3 * cm))
            continue

        # Dimension table: [CORE/IMP] Name | Level | Anchor
        rows = [["Dimension", "Level", "Anchor"]]
        for dim in expert.triggered_dimensions:
            tier_chip = "[CORE]" if dim.tier == "CORE" else "[IMP]"
            anchor_short = (
                dim.regulatory_anchor[:42] + "…"
                if len(dim.regulatory_anchor) > 42
                else dim.regulatory_anchor
            )
            rows.append([
                Paragraph(
                    f'<font size="7" color="#78716C">{tier_chip}</font>'
                    f' <b>{_esc(dim.display_name)}</b>',
                    sty_dim_name,
                ),
                Paragraph(
                    f'<font color="{_SEV_TEXT.get(dim.level, "#3B6D11")}">'
                    f'<b>{_esc(dim.level)}</b></font>',
                    sty_dim_lvl,
                ),
                Paragraph(_esc(anchor_short), sty_dim_anchor),
            ])

        col_w = [6.5 * cm, 1.8 * cm, 7.7 * cm]
        t = Table(rows, colWidths=col_w, repeatRows=1)
        sev_styles = []
        for i, dim in enumerate(expert.triggered_dimensions, 1):
            sev_styles += [
                ("BACKGROUND", (1, i), (1, i),
                 HexColor(_SEV_BG.get(dim.level, "#EAF3DE"))),
            ]
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _RULE_REF_BG),
            ("TEXTCOLOR",     (0, 0), (-1, 0), _DARK_BG),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 7),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [white, HexColor("#FAFAF9")]),
            ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#E7E5E4")),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN",         (1, 0), (1, -1), "CENTER"),
        ] + sev_styles))
        elements.append(t)

        # Reason notes
        for dim in expert.triggered_dimensions:
            if dim.reason:
                elements.append(Paragraph(
                    _esc(f"↳ {dim.display_name}: {dim.reason}"),
                    sty_reason,
                ))

        elements.append(Spacer(1, 0.5 * cm))

    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Page 4 — Regulatory Violations
# ---------------------------------------------------------------------------
def _regulatory_page(response: SAFEEvaluationResponse) -> list:
    sty_h1 = _ps("H1R", fontName="Helvetica-Bold", fontSize=14,
                 textColor=_DARK_BG, spaceBefore=4, spaceAfter=10)
    sty_body = _ps("BodyR", fontName="Helvetica", fontSize=9,
                   textColor=HexColor("#A8A29E"), spaceAfter=4)

    elements: list = []
    elements.append(Paragraph("Regulatory Violations", sty_h1))

    rows: list = [["Level", "Expert", "Dimension", "Anchor", "Evidence"]]
    for expert in response.experts:
        label = _EXPERT_DISPLAY.get(expert.id, expert.id)
        for dim in expert.triggered_dimensions:
            anchor_short = (
                dim.regulatory_anchor[:44] + "…"
                if len(dim.regulatory_anchor) > 44
                else dim.regulatory_anchor
            )
            rows.append([
                _esc(dim.level),
                _esc(label),
                _esc(dim.display_name),
                _esc(anchor_short),
                _esc(dim.evidence_quality),
            ])

    if len(rows) == 1:
        elements.append(Paragraph("No regulatory violations detected.", sty_body))
        return elements

    col_widths = [1.5 * cm, 3.5 * cm, 3.5 * cm, 5.8 * cm, 1.7 * cm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)

    # Per-row level coloring
    level_styles = []
    for i, row in enumerate(rows[1:], 1):
        lv = row[0]  # already _esc'd plain text
        bg = HexColor(_SEV_BG.get(lv, "#EAF3DE"))
        tx = HexColor(_SEV_TEXT.get(lv, "#3B6D11"))
        level_styles += [
            ("BACKGROUND", (0, i), (0, i), bg),
            ("TEXTCOLOR",  (0, i), (0, i), tx),
            ("FONTNAME",   (0, i), (0, i), "Helvetica-Bold"),
        ]

    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _DARK_BG),
        ("TEXTCOLOR",     (0, 0), (-1, 0), white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_RULE_REF_BG, white]),
        ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#E7E5E4")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
    ] + level_styles))
    elements.append(t)
    return elements


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_pdf_bytes(response: SAFEEvaluationResponse) -> bytes:
    """Generate a 4-page PDF report and return raw bytes (no file I/O)."""
    verdict = response.verdict
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story: list = []
    story.extend(_cover_page(response))
    story.extend(_exec_summary_page(response))
    story.extend(_expert_findings_page(response))
    story.extend(_regulatory_page(response))

    def _on_page(canvas, doc_):
        _cover_canvas(canvas, doc_, verdict, response)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def generate_pdf(response: SAFEEvaluationResponse, path: str) -> str:
    """Generate a 4-page PDF report and write it to *path*. Returns the path."""
    verdict = response.verdict
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story: list = []
    story.extend(_cover_page(response))
    story.extend(_exec_summary_page(response))
    story.extend(_expert_findings_page(response))
    story.extend(_regulatory_page(response))

    def _on_page(canvas, doc_):
        _cover_canvas(canvas, doc_, verdict, response)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return path
