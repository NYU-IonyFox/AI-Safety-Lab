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
from reportlab.pdfbase.pdfmetrics import stringWidth
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
# Color constants
# ---------------------------------------------------------------------------
_DARK_BG   = HexColor("#44403C")
_RULE_BG   = HexColor("#F5F0EB")

# Cover — pre-blended semitransparent whites on #44403C (68,64,60)
_CW90 = HexColor("#ECECEC")   # rgba(255,255,255,0.90)
_CW42 = HexColor("#928F8D")   # rgba(255,255,255,0.42)
_CW38 = HexColor("#8B8986")   # rgba(255,255,255,0.38)
_CW30 = HexColor("#7C7977")   # rgba(255,255,255,0.30)
_CW28 = HexColor("#787674")   # rgba(255,255,255,0.28)
_CW20 = HexColor("#696765")   # rgba(255,255,255,0.20)
_CW10 = HexColor("#575553")   # rgba(255,255,255,0.10)
_CW05 = HexColor("#4D4A46")   # rgba(255,255,255,0.05)

# Cover — badge fill (verdict colour @15% on dark bg)
_BADGE_BG = {
    "REJECT":  HexColor("#5E504C"),
    "HOLD":    HexColor("#605948"),
    "APPROVE": HexColor("#565B52"),
}

# Verdict colours
_COVER_V = {"REJECT": "#F2A8A8", "HOLD": "#FDE68A", "APPROVE": "#BBF7D0"}
_INNER_V_TEXT = {"REJECT": "#A32D2D", "HOLD": "#854F0B", "APPROVE": "#3B6D11"}
_INNER_V_BG   = {"REJECT": "#FCEBEB", "HOLD": "#FAEEDA", "APPROVE": "#EAF3DE"}

# Level — solid dark background (inner pages)
_SEV_SOLID_BG   = {"HIGH": "#A32D2D", "MEDIUM": "#854F0B", "LOW": "#3B6D11"}
_SEV_LIGHT_BG   = {"HIGH": "#FCEBEB", "MEDIUM": "#FAEEDA", "LOW": "#EAF3DE"}
_SEV_LIGHT_TEXT = {"HIGH": "#A32D2D", "MEDIUM": "#854F0B", "LOW": "#3B6D11"}

_EXPERT_COLORS = {
    "expert_adversarial_security": "#3D6070",
    "expert_content_safety":       "#4A4880",
    "expert_governance_un":        "#634078",
}
_EXPERT_DISPLAY = {
    "expert_adversarial_security": "Expert 1 — Adversarial Security",
    "expert_content_safety":       "Expert 2 — Content Safety",
    "expert_governance_un":        "Expert 3 — Governance & UN",
}
_VERDICT_BADGE = {
    "REJECT":  "Do not deploy into UNICC systems",
    "HOLD":    "Human review required",
    "APPROVE": "Cleared for UNICC deployment",
}

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _ps(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


def make_filename(response: SAFEEvaluationResponse, ext: str) -> str:
    target = response.submission_context.get("target_name", "unknown")
    target = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(target).replace(" ", "_"))[:32]
    date_str = (response.timestamp or "")[:10].replace("-", "")
    return f"{target}_{response.verdict}_{date_str}.{ext}"


def _wrap_text(text: str, max_w: float, font: str, size: float) -> list[str]:
    """Word-wrap text to fit max_w points wide."""
    words = str(text).split()
    lines: list[str] = []
    line = ""
    for w in words:
        candidate = (line + " " + w).strip() if line else w
        if stringWidth(candidate, font, size) <= max_w:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines or [""]


# ---------------------------------------------------------------------------
# Page 1 — cover (pure canvas)
# ---------------------------------------------------------------------------
def _draw_cover(canvas, doc, response: SAFEEvaluationResponse) -> None:
    if doc.page != 1:
        return
    canvas.saveState()
    W, H = A4                   # 595.27 × 841.89 pt
    verdict = response.verdict
    x0 = 60                     # left content margin

    # ── Background ──────────────────────────────────────────────────────────
    canvas.setFillColor(_DARK_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

    # ── SAFE wordmark ────────────────────────────────────────────────────────
    canvas.setFillColor(_CW90)
    canvas.setFont("Times-Bold", 18)
    canvas.drawString(x0, H - 54, "SAFE")

    canvas.setFillColor(_CW30)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(x0, H - 69, "Safety Assurance Framework for Evaluation")

    # ── Logos (best-effort) ──────────────────────────────────────────────────
    try:
        up = str(_ASSETS_DIR / "透明底白色UNICC.png")
        np = str(_ASSETS_DIR / "透明底白色NYU.png")
        ly = H - 78
        if os.path.exists(up):
            canvas.drawImage(up, W - 130, ly, width=54, height=28,
                             preserveAspectRatio=True, mask="auto")
        if os.path.exists(np):
            canvas.drawImage(np, W - 72, ly, width=46, height=28,
                             preserveAspectRatio=True, mask="auto")
    except Exception:
        pass

    # ── "EVALUATION REPORT" label ────────────────────────────────────────────
    canvas.setFillColor(_CW38)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(x0, 645, "EVALUATION REPORT")

    # ── target_name ──────────────────────────────────────────────────────────
    target = str(response.submission_context.get("target_name", "Unknown Target"))
    canvas.setFillColor(HexColor("#FAFAF8"))
    canvas.setFont("Times-Bold", 28)
    # wrap long names
    max_name_w = W - x0 - 60
    name_lines = _wrap_text(target, max_name_w, "Times-Bold", 28)
    ny = 608
    for nl in name_lines[:2]:
        canvas.drawString(x0, ny, nl)
        ny -= 34

    # ── Verdict word ─────────────────────────────────────────────────────────
    vcolor = HexColor(_COVER_V.get(verdict, "#FDE68A"))
    canvas.setFillColor(vcolor)
    canvas.setFont("Times-Bold", 80)
    canvas.drawString(x0, 490, verdict)

    # ── Verdict badge ─────────────────────────────────────────────────────────
    badge_text = _VERDICT_BADGE.get(verdict, "")
    badge_bg = _BADGE_BG.get(verdict, HexColor("#605948"))
    badge_h = 22
    badge_y = 452
    badge_w = min(int(stringWidth(badge_text, "Helvetica", 11)) + 24, int(W - x0 - 60))
    canvas.setFillColor(badge_bg)
    canvas.roundRect(x0, badge_y, badge_w, badge_h, 4, fill=1, stroke=0)
    canvas.setFillColor(vcolor)
    canvas.setFont("Helvetica", 11)
    canvas.drawString(x0 + 12, badge_y + 6, badge_text)

    # ── Primary reason block ──────────────────────────────────────────────────
    rule_text = str(response.primary_reason.get(
        "decision_rule_triggered",
        response.primary_reason.get("rule", "—")
    ))
    pr_x = x0
    pr_w = W - x0 - 60
    pr_line_h = 14
    rule_lines = _wrap_text(rule_text, pr_w - 24, "Helvetica", 10)[:3]
    pr_h = max(36, len(rule_lines) * pr_line_h + 18)
    pr_y = badge_y - 10 - pr_h

    canvas.setFillColor(_CW05)
    canvas.rect(pr_x, pr_y, pr_w, pr_h, fill=1, stroke=0)
    canvas.setStrokeColor(_CW20)
    canvas.setLineWidth(2)
    canvas.line(pr_x, pr_y, pr_x, pr_y + pr_h)
    canvas.setLineWidth(0.5)

    canvas.setFillColor(_CW42)
    canvas.setFont("Helvetica", 10)
    ty = pr_y + pr_h - 14
    for rl in rule_lines:
        canvas.drawString(pr_x + 12, ty, rl)
        ty -= pr_line_h

    # ── Footer ────────────────────────────────────────────────────────────────
    canvas.setStrokeColor(_CW10)
    canvas.line(x0, 52, W - x0, 52)

    canvas.setFillColor(_CW28)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(x0, 36, "SAFE v1.2 · UNICC AI Safety Lab")
    ts = (response.timestamp or "")[:10]
    eid = response.evaluation_id or "—"
    canvas.drawRightString(W - x0, 36, f"Evaluation ID: {eid} · {ts}")

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Pages 2-4 header callback
# ---------------------------------------------------------------------------
def _draw_inner_header(canvas, doc, response: SAFEEvaluationResponse) -> None:
    if doc.page == 1:
        return
    canvas.saveState()
    W, H = A4
    x0 = 2 * cm   # left margin

    # SAFE
    canvas.setFillColor(_DARK_BG)
    canvas.setFont("Times-Bold", 13)
    canvas.drawString(x0, H - 26, "SAFE")

    # "Evaluation Report"
    sw = stringWidth("SAFE", "Times-Bold", 13)
    canvas.setFillColor(HexColor("#A8A29E"))
    canvas.setFont("Helvetica", 10)
    canvas.drawString(x0 + sw + 8, H - 26, "Evaluation Report")

    # Right: target · verdict
    target = str(response.submission_context.get("target_name", ""))
    v = response.verdict
    meta = f"{target} · {v}" if target else v
    canvas.setFillColor(HexColor("#C8C0B8"))
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(W - 2 * cm, H - 26, meta)

    # Separator
    canvas.setStrokeColor(HexColor("#E7E5E4"))
    canvas.setLineWidth(0.5)
    canvas.line(x0, H - 34, W - 2 * cm, H - 34)

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Page 2 — Executive Summary
# ---------------------------------------------------------------------------
def _exec_summary_page(response: SAFEEvaluationResponse) -> list:
    verdict = response.verdict
    vtext  = HexColor(_INNER_V_TEXT.get(verdict, "#854F0B"))
    vbg    = HexColor(_INNER_V_BG.get(verdict,   "#FAEEDA"))
    vsolid = HexColor(_SEV_SOLID_BG.get(verdict,  "#854F0B"))
    badge_text = _VERDICT_BADGE.get(verdict, "")
    rule_text  = str(response.primary_reason.get(
        "decision_rule_triggered",
        response.primary_reason.get("rule", "—")
    ))
    sc = response.submission_context or {}

    s_h1      = _ps("H1E",   fontName="Helvetica-Bold", fontSize=14, textColor=_DARK_BG,  spaceBefore=4,  spaceAfter=8)
    s_label   = _ps("LblE",  fontName="Helvetica-Bold", fontSize=8,  textColor=HexColor("#A8A29E"), spaceAfter=3,
                    textTransform="uppercase")
    s_verd    = _ps("VerdE", fontName="Times-Bold",     fontSize=48, textColor=vtext,  spaceAfter=6, leading=54)
    s_badge   = _ps("BdgE",  fontName="Helvetica-Bold", fontSize=9,  textColor=white,   spaceAfter=6)
    s_rule    = _ps("RuleE", fontName="Helvetica",      fontSize=10, textColor=HexColor("#78716C"),
                    spaceAfter=4, leading=14)
    s_meta    = _ps("MetaE", fontName="Helvetica",      fontSize=9,  textColor=HexColor("#A8A29E"), spaceAfter=10, leading=13)
    s_h2      = _ps("H2E",   fontName="Helvetica-Bold", fontSize=11, textColor=_DARK_BG,  spaceBefore=10, spaceAfter=5)
    s_body    = _ps("BdyE",  fontName="Helvetica",      fontSize=9,  textColor=black,     leading=14, spaceAfter=4)
    s_rec     = _ps("RecE",  fontName="Helvetica",      fontSize=10, textColor=HexColor("#1C1917"), leading=16, spaceAfter=3)
    s_rec_num = _ps("RnE",   fontName="Helvetica-Bold", fontSize=10, textColor=_DARK_BG,  spaceAfter=3)

    elems: list = []
    elems.append(Paragraph("Executive Summary", s_h1))

    # ── Verdict hero (2-column) ──────────────────────────────────────────────
    # Left: label + verdict word + badge
    badge_block = Table(
        [[Paragraph(_esc(badge_text), s_badge)]],
        colWidths=[6 * cm],
    )
    badge_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), vsolid),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BORDERRADIUS", (0, 0), (-1, -1), 3),
    ]))

    left_col = [
        Paragraph("VERDICT", s_label),
        Paragraph(_esc(verdict), s_verd),
        badge_block,
    ]

    # Right: primary reason
    rule_block = Table(
        [[Paragraph(_esc(rule_text), s_rule)]],
        colWidths=[9 * cm],
    )
    rule_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _RULE_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBEFORE", (0, 0), (0, -1), 2, _DARK_BG),
    ]))

    right_col = [
        Paragraph("PRIMARY DECISION REASON", s_label),
        rule_block,
    ]

    # Nested table: left_col | right_col
    from reportlab.platypus import KeepTogether
    hero = Table(
        [[left_col, right_col]],
        colWidths=[6.5 * cm, 9.5 * cm],
    )
    hero.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 12),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(hero)
    elems.append(Spacer(1, 0.3 * cm))

    # ── Metadata row ─────────────────────────────────────────────────────────
    input_type = sc.get("source_type", sc.get("input_type", "—"))
    ts = (response.timestamp or "")[:19].replace("T", " ")
    meta_str = (
        f"Input type: {input_type}  ·  Mode: LLM API"
        f"  ·  ID: {response.evaluation_id}  ·  {ts}"
    )
    elems.append(Paragraph(_esc(meta_str), s_meta))

    # ── Expert Risk Summary ──────────────────────────────────────────────────
    expert_summary = response.primary_reason.get("expert_summary", {})
    if expert_summary:
        s_rl = _ps("H2RL",  fontName="Helvetica-Bold", fontSize=10,
                   textColor=_DARK_BG, spaceBefore=10, spaceAfter=5,
                   borderPadding=(0, 0, 0, 10),
                   borderLeftColor=_DARK_BG, borderLeftWidth=3)
        elems.append(Paragraph("EXPERT RISK LEVELS", _ps("RlLbl", fontName="Helvetica-Bold",
                                                          fontSize=10, textColor=_DARK_BG,
                                                          spaceBefore=10, spaceAfter=5)))
        rows = [["Expert", "Risk Level"]]
        for slot, level in expert_summary.items():
            label = _EXPERT_DISPLAY.get(slot, slot)
            rows.append([_esc(str(label)), _esc(str(level))])
        t = Table(rows, colWidths=[11 * cm, 5 * cm])
        lv_styles = []
        for i, row in enumerate(rows[1:], 1):
            lv = row[1]
            lv_styles += [
                ("BACKGROUND", (1, i), (1, i),
                 HexColor(_SEV_SOLID_BG.get(lv, "#3B6D11"))),
                ("TEXTCOLOR",  (1, i), (1, i), white),
                ("FONTNAME",   (1, i), (1, i), "Helvetica-Bold"),
            ]
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _RULE_BG),
            ("TEXTCOLOR",     (0, 0), (-1, 0), _DARK_BG),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [white, HexColor("#FAFAF9")]),
            ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#E7E5E4")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN",         (1, 0), (1, -1), "CENTER"),
        ] + lv_styles))
        elems.append(t)
        elems.append(Spacer(1, 0.4 * cm))

    # ── Additional findings ──────────────────────────────────────────────────
    if response.additional_findings:
        elems.append(Paragraph("Additional Findings", _ps("H2AF", fontName="Helvetica-Bold",
                                                           fontSize=11, textColor=_DARK_BG,
                                                           spaceBefore=10, spaceAfter=5)))
        for f in response.additional_findings:
            elems.append(Paragraph(_esc(f"• {f}"), s_body))

    # ── Recommendations ──────────────────────────────────────────────────────
    elems.append(Paragraph("Recommendations", _ps("H2Rec", fontName="Helvetica-Bold",
                                                   fontSize=11, textColor=_DARK_BG,
                                                   spaceBefore=10, spaceAfter=5,
                                                   borderPadding=(0, 0, 0, 10),
                                                   borderLeftColor=_DARK_BG, borderLeftWidth=3)))
    if response.recommendations:
        for i, rec in enumerate(response.recommendations, 1):
            txt = rec.get("text", "")
            src = rec.get("source_expert", "")
            dim = rec.get("source_dimension", "")
            src_label = f"— {src}" + (f" · {dim}" if dim else "")
            body = _esc(str(txt))
            if src:
                body += (f'<br/><font color="#78716C" size="9">'
                         f'<i>{_esc(src_label)}</i></font>')
            row = Table(
                [[Paragraph(f"{i}.", s_rec_num),
                  Paragraph(body, s_rec)]],
                colWidths=[0.7 * cm, 15.3 * cm],
            )
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING",   (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ]))
            elems.append(row)
    else:
        elems.append(Paragraph("No recommendations generated.", s_body))

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# Page 3 — Expert Council Findings
# ---------------------------------------------------------------------------
def _expert_findings_page(response: SAFEEvaluationResponse) -> list:
    s_h1     = _ps("H1F", fontName="Helvetica-Bold", fontSize=14, textColor=_DARK_BG, spaceBefore=4, spaceAfter=10)
    s_name   = _ps("ExNm", fontName="Helvetica-Bold", fontSize=13, textColor=HexColor("#1C1917"), spaceAfter=4)
    s_none   = _ps("NoneF", fontName="Helvetica-Oblique", fontSize=9, textColor=HexColor("#78716C"), spaceAfter=6)
    s_reason = _ps("RsnF", fontName="Helvetica", fontSize=9, textColor=HexColor("#44403C"),
                   leading=14, spaceAfter=3, leftIndent=10)
    s_anchor = _ps("AnkF", fontName="Helvetica", fontSize=8, textColor=HexColor("#78716C"), leading=11)
    s_dim    = _ps("DimF", fontName="Helvetica-Bold", fontSize=9, textColor=HexColor("#1C1917"), leading=13)

    elems: list = []
    elems.append(Paragraph("Expert Council Findings", s_h1))

    for expert in response.experts:
        ec = HexColor(_EXPERT_COLORS.get(expert.id, "#44403C"))
        label = _EXPERT_DISPLAY.get(expert.id, expert.id)
        level = expert.overall

        # Colour bar strip
        bar = Table([[""]], colWidths=[16 * cm])
        bar.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), ec),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        elems.append(bar)

        # Title row: name + overall badge
        lv_bg = HexColor(_SEV_SOLID_BG.get(level, "#3B6D11"))
        badge_p = Table(
            [[Paragraph(_esc(level), _ps("OvF", fontName="Helvetica-Bold",
                                          fontSize=8, textColor=white))]],
            colWidths=[1.8 * cm],
        )
        badge_p.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), lv_bg),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        title_row = Table(
            [[Paragraph(_esc(label), s_name), badge_p]],
            colWidths=[13.2 * cm, 2.8 * cm],
        )
        title_row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
        ]))
        elems.append(title_row)

        if not expert.triggered_dimensions:
            elems.append(Paragraph(
                "No dimensions triggered — all within acceptable range.", s_none))
            elems.append(Spacer(1, 0.3 * cm))
            continue

        # Dimension rows
        for dim in expert.triggered_dimensions:
            tier_chip = "[CORE]" if dim.tier == "CORE" else "[IMP]"
            dv_bg  = HexColor(_SEV_SOLID_BG.get(dim.level, "#3B6D11"))
            anchor = (dim.regulatory_anchor[:46] + "…"
                      if len(dim.regulatory_anchor) > 46
                      else dim.regulatory_anchor)

            dim_badge = Table(
                [[Paragraph(_esc(dim.level),
                             _ps("DbF_" + dim.name,
                                 fontName="Helvetica-Bold", fontSize=8, textColor=white))]],
                colWidths=[1.6 * cm],
            )
            dim_badge.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), dv_bg),
                ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))

            dim_row = Table(
                [[
                    Paragraph(
                        f'<font size="8" color="#78716C">{tier_chip}</font>'
                        f' <b>{_esc(dim.display_name)}</b>',
                        s_dim
                    ),
                    dim_badge,
                    Paragraph(_esc(anchor), s_anchor),
                ]],
                colWidths=[5.5 * cm, 1.8 * cm, 8.7 * cm],
            )
            dim_row.setStyle(TableStyle([
                ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#E7E5E4")),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS",(0, 0), (-1, -1), [white]),
            ]))
            elems.append(dim_row)

            if dim.reason:
                elems.append(Paragraph(_esc(f"↳ {dim.reason}"), s_reason))

        elems.append(Spacer(1, 0.5 * cm))

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# Page 4 — Regulatory Violations
# ---------------------------------------------------------------------------
def _regulatory_page(response: SAFEEvaluationResponse) -> list:
    s_h1   = _ps("H1R", fontName="Helvetica-Bold", fontSize=14, textColor=_DARK_BG, spaceBefore=4, spaceAfter=10)
    s_none = _ps("NoneR", fontName="Helvetica", fontSize=9, textColor=HexColor("#A8A29E"), spaceAfter=4)

    elems: list = []
    elems.append(Paragraph("Regulatory Violations", s_h1))

    rows: list = [["Level", "Expert", "Dimension", "Anchor"]]
    for expert in response.experts:
        label = _EXPERT_DISPLAY.get(expert.id, expert.id)
        for dim in expert.triggered_dimensions:
            anchor = (dim.regulatory_anchor[:48] + "…"
                      if len(dim.regulatory_anchor) > 48
                      else dim.regulatory_anchor)
            rows.append([
                _esc(dim.level),
                _esc(label),
                _esc(dim.display_name),
                _esc(anchor),
            ])

    if len(rows) == 1:
        elems.append(Paragraph("No regulatory violations detected.", s_none))
        return elems

    col_widths = [1.6 * cm, 3.8 * cm, 4.0 * cm, 6.6 * cm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)

    lv_styles = []
    for i, row in enumerate(rows[1:], 1):
        lv = row[0]
        lv_styles += [
            ("BACKGROUND", (0, i), (0, i), HexColor(_SEV_SOLID_BG.get(lv, "#3B6D11"))),
            ("TEXTCOLOR",  (0, i), (0, i), white),
            ("FONTNAME",   (0, i), (0, i), "Helvetica-Bold"),
        ]

    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _DARK_BG),
        ("TEXTCOLOR",     (0, 0), (-1, 0), white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_RULE_BG, white]),
        ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#E7E5E4")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
    ] + lv_styles))
    elems.append(t)
    return elems


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_pdf_bytes(response: SAFEEvaluationResponse) -> bytes:
    """Generate a 4-page PDF report and return raw bytes (no file I/O)."""
    buf = BytesIO()
    _build_doc(response, buf)
    return buf.getvalue()


def generate_pdf(response: SAFEEvaluationResponse, path: str) -> str:
    """Generate a 4-page PDF report and write it to *path*. Returns the path."""
    _build_doc(response, path)
    return path


def _build_doc(response: SAFEEvaluationResponse, dest) -> None:
    doc = SimpleDocTemplate(
        dest,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    # Page 1: tiny spacer + PageBreak commits the page so onFirstPage fires,
    # then all content flows onto pages 2-4.
    story: list = [Spacer(1, 1), PageBreak()]
    story.extend(_exec_summary_page(response))
    story.extend(_expert_findings_page(response))
    story.extend(_regulatory_page(response))

    def _on_page(canvas, doc_):
        _draw_cover(canvas, doc_, response)
        _draw_inner_header(canvas, doc_, response)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
