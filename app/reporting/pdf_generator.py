from __future__ import annotations

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
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
# Verdict color palette
# ---------------------------------------------------------------------------
_COLORS: dict[str, dict] = {
    "REJECT":  {"text": HexColor("#A32D2D"), "accent": HexColor("#FCEBEB")},
    "HOLD":    {"text": HexColor("#854F0B"), "accent": HexColor("#FAEEDA")},
    "APPROVE": {"text": HexColor("#3B6D11"), "accent": HexColor("#EAF3DE")},
}
_DARK_BG = HexColor("#44403C")

_EXPERT_DISPLAY = {
    "expert_adversarial_security": "Expert 1 — Adversarial Security",
    "expert_content_safety":       "Expert 2 — Content Safety",
    "expert_governance_un":        "Expert 3 — Governance & UN",
}


def _esc(text: str) -> str:
    """Escape XML special chars for ReportLab Paragraph."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _styles(verdict: str) -> dict[str, ParagraphStyle]:
    c = _COLORS.get(verdict, _COLORS["HOLD"])
    base = getSampleStyleSheet()

    def _ps(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    return {
        "title": _ps(
            "Title",
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=white,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "verdict_large": _ps(
            "VerdictLarge",
            fontName="Helvetica-Bold",
            fontSize=48,
            textColor=c["text"],
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "h1": _ps(
            "H1",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=c["text"],
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h2": _ps(
            "H2",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=black,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": _ps(
            "Body",
            fontName="Helvetica",
            fontSize=9,
            textColor=black,
            leading=14,
            spaceAfter=4,
        ),
        "small": _ps(
            "Small",
            fontName="Helvetica",
            fontSize=8,
            textColor=HexColor("#555555"),
            leading=12,
            spaceAfter=2,
        ),
        "cover_meta": _ps(
            "CoverMeta",
            fontName="Helvetica",
            fontSize=10,
            textColor=white,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
    }


def _cover_page(response: SAFEEvaluationResponse, sty: dict, verdict_colors: dict) -> list:
    target = response.submission_context.get("target_name", "Unknown Target")
    rule_text = response.primary_reason.get("rule", "—")

    elements = []
    elements.append(Spacer(1, 3 * cm))
    elements.append(Paragraph("SAFE Evaluation Report", sty["title"]))
    elements.append(Spacer(1, 0.4 * cm))
    elements.append(Paragraph(_esc(f"Target: {target}"), sty["cover_meta"]))
    elements.append(Spacer(1, 1.0 * cm))
    elements.append(Paragraph(_esc(response.verdict), sty["verdict_large"]))
    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph(_esc(f"Rule applied: {rule_text}"), sty["cover_meta"]))
    elements.append(Spacer(1, 1.5 * cm))
    elements.append(Paragraph(_esc(f"Evaluation ID: {response.evaluation_id}"), sty["cover_meta"]))
    elements.append(Paragraph(_esc(f"Timestamp: {response.timestamp}"), sty["cover_meta"]))
    elements.append(Paragraph(_esc(f"SAFE version: {response.safe_version}"), sty["cover_meta"]))
    elements.append(PageBreak())
    return elements


def _exec_summary_page(response: SAFEEvaluationResponse, sty: dict) -> list:
    elements = []
    elements.append(Paragraph("Executive Summary", sty["h1"]))
    elements.append(Paragraph(
        _esc(f"Verdict: {response.verdict}"),
        sty["h2"],
    ))
    rule = response.primary_reason.get("rule", "—")
    elements.append(Paragraph(_esc(f"Decision rule: {rule}"), sty["body"]))

    expert_summary = response.primary_reason.get("expert_summary", {})
    if expert_summary:
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph("Expert risk levels:", sty["h2"]))
        for slot, level in expert_summary.items():
            elements.append(Paragraph(_esc(f"  • {slot}: {level}"), sty["body"]))

    if response.additional_findings:
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph("Additional Findings", sty["h2"]))
        for finding in response.additional_findings:
            elements.append(Paragraph(_esc(f"• {finding}"), sty["body"]))

    if response.recommendations:
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph("Recommendations", sty["h2"]))
        for rec in response.recommendations:
            text = rec.get("text", "")
            src = rec.get("source_expert", "")
            dim = rec.get("source_dimension", "")
            elements.append(Paragraph(
                _esc(f"• {text} [{src} / {dim}]"),
                sty["body"],
            ))
    else:
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph("No specific remediation recommendations generated.", sty["body"]))

    elements.append(PageBreak())
    return elements


def _expert_findings_page(response: SAFEEvaluationResponse, sty: dict) -> list:
    elements = []
    elements.append(Paragraph("Expert Council Findings", sty["h1"]))

    for expert in response.experts:
        label = _EXPERT_DISPLAY.get(expert.id, expert.id)
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph(_esc(f"{label}  —  Overall: {expert.overall}"), sty["h2"]))

        if not expert.triggered_dimensions:
            elements.append(Paragraph("No dimensions triggered (all LOW).", sty["small"]))
            continue

        for dim in expert.triggered_dimensions:
            elements.append(Paragraph(
                _esc(
                    f"  [{dim.tier}] {dim.display_name}  |  {dim.level}  |  "
                    f"Evidence: {dim.evidence_quality}  |  Anchor: {dim.regulatory_anchor}"
                ),
                sty["small"],
            ))
            if dim.reason:
                elements.append(Paragraph(_esc(f"    Reason: {dim.reason}"), sty["small"]))

    elements.append(PageBreak())
    return elements


def _regulatory_page(response: SAFEEvaluationResponse, sty: dict) -> list:
    elements = []
    elements.append(Paragraph("Regulatory Violations Summary", sty["h1"]))

    rows = [["Expert", "Dimension", "Level", "Regulatory Anchor", "Evidence"]]
    for expert in response.experts:
        label = _EXPERT_DISPLAY.get(expert.id, expert.id)
        for dim in expert.triggered_dimensions:
            rows.append([
                _esc(label),
                _esc(dim.display_name),
                _esc(dim.level),
                _esc(dim.regulatory_anchor),
                _esc(dim.evidence_quality),
            ])

    if len(rows) == 1:
        elements.append(Paragraph("No regulatory violations detected.", sty["body"]))
    else:
        col_widths = [3.5 * cm, 4.0 * cm, 1.5 * cm, 5.5 * cm, 2.0 * cm]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#44403C")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#F5F5F5")]),
            ("GRID",       (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("WORDWRAP",   (0, 0), (-1, -1), "WORD"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ]))
        elements.append(t)

    return elements


def _cover_background(canvas, doc, verdict: str) -> None:
    """Draw dark background only on page 1 (cover)."""
    if doc.page == 1:
        canvas.saveState()
        canvas.setFillColor(_DARK_BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()


def generate_pdf_bytes(response: SAFEEvaluationResponse) -> bytes:
    """Generate a 4-page PDF report and return it as raw bytes (no file I/O)."""
    from io import BytesIO
    verdict = response.verdict
    sty = _styles(verdict)
    vc = _COLORS.get(verdict, _COLORS["HOLD"])

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
    story.extend(_cover_page(response, sty, vc))
    story.extend(_exec_summary_page(response, sty))
    story.extend(_expert_findings_page(response, sty))
    story.extend(_regulatory_page(response, sty))

    def _on_page(canvas, doc_):
        _cover_background(canvas, doc_, verdict)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()


def generate_pdf(response: SAFEEvaluationResponse, path: str) -> str:
    """Generate a 4-page PDF report and write it to *path*. Returns the path."""
    verdict = response.verdict
    sty = _styles(verdict)
    vc = _COLORS.get(verdict, _COLORS["HOLD"])

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: list = []
    story.extend(_cover_page(response, sty, vc))
    story.extend(_exec_summary_page(response, sty))
    story.extend(_expert_findings_page(response, sty))
    story.extend(_regulatory_page(response, sty))

    def _on_page(canvas, doc_):
        _cover_background(canvas, doc_, verdict)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return path
