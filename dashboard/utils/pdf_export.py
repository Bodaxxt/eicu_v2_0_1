"""
ICU Guard v5.0 — PDF Export Utility
=====================================
Generates a professional multi-page PDF clinical report using ReportLab.

Sections:
1. Cover page — patient ID, triage tier, timestamp
2. Risk Summary — ML probabilities + severity score
3. Organ System Status — 11 organ table
4. Clinical Syndromes — detected patterns
5. Action Plan — sorted by urgency
6. Narrative — English full text
7. Uncertainty Audit — reliability tier + scores
8. SBAR Handoff
9. Regulatory Disclaimer
"""

from __future__ import annotations
import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Colours ────────────────────────────────────────────────────────────────────
_DARK_BG    = colors.HexColor("#0b1120")
_CARD_BG    = colors.HexColor("#1e293b")
_ACCENT     = colors.HexColor("#6366f1")
_CYAN       = colors.HexColor("#06b6d4")
_TEXT       = colors.HexColor("#e2e8f0")
_SUBTEXT    = colors.HexColor("#94a3b8")
_CRITICAL   = colors.HexColor("#ef4444")
_HIGH       = colors.HexColor("#f97316")
_MODERATE   = colors.HexColor("#eab308")
_STABLE     = colors.HexColor("#22c55e")
_WHITE      = colors.white

_TIER_COLOURS = {
    "CRITICAL": _CRITICAL,
    "HIGH":     _HIGH,
    "MODERATE": _MODERATE,
    "STABLE":   _STABLE,
}

_URGENCY_COLOURS = {
    "STAT":    _CRITICAL,
    "15_MIN":  _HIGH,
    "1_HOUR":  _MODERATE,
    "ROUTINE": _STABLE,
}


# ── Style helpers ──────────────────────────────────────────────────────────────
def _make_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Normal"],
            fontSize=22, textColor=_WHITE, fontName="Helvetica-Bold",
            spaceAfter=4, alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontSize=11, textColor=_SUBTEXT, fontName="Helvetica",
            spaceAfter=2, alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "section", parent=base["Normal"],
            fontSize=13, textColor=_CYAN, fontName="Helvetica-Bold",
            spaceBefore=14, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=9, textColor=_TEXT, fontName="Helvetica",
            spaceAfter=4, leading=14,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"],
            fontSize=8, textColor=_SUBTEXT, fontName="Helvetica",
            spaceAfter=2, leading=11,
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["Normal"],
            fontSize=8, textColor=_SUBTEXT, fontName="Courier",
            spaceAfter=2, leading=11,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer", parent=base["Normal"],
            fontSize=7.5, textColor=colors.HexColor("#64748b"),
            fontName="Helvetica-Oblique", spaceAfter=2, leading=11,
        ),
    }


def _hr() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#334155"), spaceAfter=4)


# ── Main Export Function ───────────────────────────────────────────────────────
def export_pdf(
    patient_id: Any,
    assessment_dict: Dict[str, Any],
    patient_vitals: Dict[str, Any],
    english_report: str = "",
    sbar_text: str = "",
    output_path: Optional[str] = None,
) -> bytes:
    """Generate the full ICU Guard PDF report and return raw bytes.

    Args:
        patient_id:       Patient identifier string.
        assessment_dict:  ``FullClinicalAssessment.to_dict()`` output.
        patient_vitals:   Raw vitals row dict.
        english_report:   Pre-generated English narrative string.
        sbar_text:        Pre-generated SBAR string.
        output_path:      If provided, also write the PDF to this file path.

    Returns:
        PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=2 * cm,
        bottomMargin=1.8 * cm,
    )
    S = _make_styles()
    story: List = []
    W = A4[0] - 3.6 * cm  # usable width

    # ── 1. Cover page ──────────────────────────────────────────────────────────
    tier = assessment_dict.get("severity_tier", "UNKNOWN")
    tier_color = _TIER_COLOURS.get(tier, _ACCENT)
    score = assessment_dict.get("overall_score", 0.0)
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M")

    story.append(Spacer(1, 30))
    story.append(Paragraph("ICU GUARD v5.0", S["title"]))
    story.append(Paragraph("Clinical Decision Support Report", S["subtitle"]))
    story.append(Spacer(1, 8))
    story.append(_hr())
    story.append(Spacer(1, 8))

    cover_data = [
        ["Patient ID", str(patient_id)],
        ["Generated", ts],
        ["Severity Tier", tier],
        ["Composite Score", f"{score:.1f} / 10.0"],
        ["Primary Etiology", assessment_dict.get("primary_etiology", "—")],
        ["Trajectory", assessment_dict.get("trajectory", "—")],
    ]
    cover_tbl = Table(cover_data, colWidths=[5 * cm, W - 5 * cm])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), colors.HexColor("#0f172a")),
        ("BACKGROUND",  (1, 0), (1, -1), colors.HexColor("#1e293b")),
        ("TEXTCOLOR",   (0, 0), (0, -1), _SUBTEXT),
        ("TEXTCOLOR",   (1, 0), (1, -1), _TEXT),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#0f172a"), colors.HexColor("#1e293b")]),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#334155")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        # Highlight tier row
        ("BACKGROUND",  (1, 2), (1, 2), tier_color),
        ("TEXTCOLOR",   (1, 2), (1, 2), _WHITE),
        ("FONTNAME",    (1, 2), (1, 2), "Helvetica-Bold"),
    ]))
    story.append(cover_tbl)
    story.append(PageBreak())

    # ── 2. Risk Summary ────────────────────────────────────────────────────────
    story.append(Paragraph("1. PREDICTIVE RISK PROFILE", S["section"]))
    story.append(_hr())
    probs = assessment_dict.get("probabilities", {})
    risk_data = [
        ["Metric", "Probability", "Interpretation"],
        ["28-Day Mortality", f"{probs.get('p_mortality', 0)*100:.1f}%", _tier_text(probs.get('p_mortality', 0))],
        ["12h Deterioration", f"{probs.get('p_deterioration', 0)*100:.1f}%", _tier_text(probs.get('p_deterioration', 0))],
        ["Severe Disease Index", f"{probs.get('p_severe', 0)*100:.1f}%", _tier_text(probs.get('p_severe', 0))],
        ["Composite Severity", f"{score:.1f} / 10", tier],
    ]
    risk_tbl = _make_table(risk_data, col_widths=[6 * cm, 4 * cm, W - 10 * cm])
    story.append(risk_tbl)

    # Escalation
    if assessment_dict.get("escalation_occurred"):
        story.append(Spacer(1, 6))
        story.append(Paragraph("⚠ Safety Override Active", S["section"]))
        for r in assessment_dict.get("escalation_reasons", []):
            story.append(Paragraph(f"• {r}", S["body"]))

    story.append(Spacer(1, 10))

    # ── 3. Organ Systems ───────────────────────────────────────────────────────
    story.append(Paragraph("2. ORGAN SYSTEM STATUS (11 Subsystems)", S["section"]))
    story.append(_hr())
    organs = assessment_dict.get("organs", {})
    org_data = [["System", "Grade", "Description", "Key Evidence"]]
    for name, info in organs.items():
        grade = info.get("grade", 0)
        desc  = info.get("description", "")
        evid  = "; ".join(info.get("evidence", [])[:2])
        org_data.append([name, str(grade), desc[:60], evid[:70]])
    org_tbl = _make_table(org_data, col_widths=[3.5*cm, 1.5*cm, 6*cm, W-11*cm])
    _color_grade_column(org_tbl, col=1, data=org_data)
    story.append(org_tbl)

    # ── 4. Clinical Syndromes ──────────────────────────────────────────────────
    story.append(Paragraph("3. DETECTED CLINICAL SYNDROMES", S["section"]))
    story.append(_hr())
    pats = assessment_dict.get("patterns", [])
    if pats:
        pat_data = [["Syndrome", "Confidence", "Urgency", "Recommendation"]]
        for p in pats:
            pat_data.append([
                p.get("name", "")[:40],
                p.get("confidence", ""),
                p.get("urgency", ""),
                p.get("recommendation", "")[:60],
            ])
        story.append(_make_table(pat_data, col_widths=[5*cm, 2.5*cm, 2.5*cm, W-10*cm]))
    else:
        story.append(Paragraph("No high-risk syndromes detected.", S["body"]))

    story.append(Spacer(1, 10))

    # ── 5. Action Plan ─────────────────────────────────────────────────────────
    story.append(Paragraph("4. CLINICAL ACTION PLAN", S["section"]))
    story.append(_hr())
    recs = assessment_dict.get("recommendations", {})
    if recs:
        story.append(Paragraph(f"Protocol: {recs.get('protocol', '')}", S["body"]))
        story.append(Spacer(1, 4))
        for act in recs.get("stat_actions", []):
            story.append(Paragraph(f"[STAT] {act}", S["body"]))
        for caution in recs.get("cautions", []):
            story.append(Paragraph(f"⚠ {caution}", S["small"]))
    else:
        story.append(Paragraph("Standard surveillance protocol — no active bundles.", S["body"]))

    story.append(PageBreak())

    # ── 6. English Narrative ───────────────────────────────────────────────────
    if english_report:
        story.append(Paragraph("5. FULL CLINICAL NARRATIVE (English)", S["section"]))
        story.append(_hr())
        for line in english_report.split("\n"):
            if line.startswith("="):
                continue
            story.append(Paragraph(line or " ", S["mono"]))
        story.append(PageBreak())

    # ── 7. Uncertainty ─────────────────────────────────────────────────────────
    unc = assessment_dict.get("uncertainty")
    if unc:
        story.append(Paragraph("6. MODEL UNCERTAINTY AUDIT", S["section"]))
        story.append(_hr())
        u_data = [
            ["Reliability Tier", unc.get("reliability_tier", "—")],
            ["Composite Uncertainty", f"{unc.get('composite_uncertainty', 0)*100:.1f}%"],
            ["Epistemic Score", f"{unc.get('epistemic_uncertainty', 0)*100:.1f}%"],
            ["Aleatoric Score", f"{unc.get('aleatoric_uncertainty', 0)*100:.1f}%"],
            ["OOD Score", f"{unc.get('ood_score', 0)*100:.1f}%"],
        ]
        story.append(_make_table(u_data, col_widths=[6*cm, W-6*cm]))
        if unc.get("advisory"):
            story.append(Spacer(1, 6))
            story.append(Paragraph(unc["advisory"], S["small"]))
        story.append(Spacer(1, 10))

    # ── 8. SBAR ────────────────────────────────────────────────────────────────
    if sbar_text:
        story.append(Paragraph("7. SBAR SHIFT HANDOFF REPORT", S["section"]))
        story.append(_hr())
        for line in sbar_text.split("\n"):
            if line.startswith("="):
                continue
            story.append(Paragraph(line or " ", S["mono"]))
        story.append(Spacer(1, 10))

    # ── 9. Disclaimer ──────────────────────────────────────────────────────────
    story.append(_hr())
    story.append(Paragraph(
        "REGULATORY DISCLAIMER: ICU Guard v5.0 is an investigational Software as a Medical Device (SaMD) "
        "intended exclusively as a clinical decision support tool for licensed critical care physicians. "
        "It does not replace bedside clinical examination or physician judgement. "
        "Final care decisions remain entirely the responsibility of the treating clinician.",
        S["disclaimer"],
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes


# ── Helper utilities ───────────────────────────────────────────────────────────
def _tier_text(prob: float) -> str:
    if prob >= 0.7:
        return "CRITICAL"
    if prob >= 0.5:
        return "HIGH"
    if prob >= 0.3:
        return "MODERATE"
    return "LOW"


def _make_table(data: List[List], col_widths: List) -> Table:
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), _CYAN),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR",     (0, 1), (-1, -1), _TEXT),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0f172a"), colors.HexColor("#1e293b")]),
        ("GRID",          (0, 0), (-1, -1), 0.25, colors.HexColor("#334155")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _color_grade_column(tbl: Table, col: int, data: List[List]) -> None:
    """Apply per-row background to a grade column based on value."""
    grade_bg = {0: colors.HexColor("#14532d"), 1: colors.HexColor("#713f12"), 2: colors.HexColor("#7f1d1d")}
    for i, row in enumerate(data[1:], start=1):
        try:
            g = int(row[col])
            bg = grade_bg.get(g, colors.HexColor("#1e293b"))
            tbl.setStyle(TableStyle([("BACKGROUND", (col, i), (col, i), bg)]))
        except (ValueError, IndexError):
            pass
