"""
ICU Guard v5.0 — Organ Cards Component
Renders the 11 evidence-based physiological organ failure detectors
with clinical injury grades (0-3), evidence findings, progress bars, and guideline references.
"""

from typing import Dict, Any
from nicegui import ui
from dashboard.utils.constants import TIER_COLORS, TIER_CRITICAL, TIER_HIGH, TIER_MODERATE, TIER_STABLE

ORGAN_ICONS = {
    "Respiratory": "🫁",
    "Hemodynamic": "❤️",
    "Renal": "🫘",
    "Neurological": "🧠",
    "Sepsis": "🦠",
    "Hepatic": "🫀",
    "Coagulation": "🩸",
    "Metabolic": "⚗️",
    "Endocrine": "🧬",
    "Hematologic": "🩸",
    "Nutritional": "🍎",
}

GRADE_COLORS = {
    0: ("#32CD32", "Grade 0: Normal"),
    1: ("#FFD700", "Grade 1: Mild Stress"),
    2: ("#FF8C00", "Grade 2: Moderate Injury"),
    3: ("#DC143C", "Grade 3: Severe Failure"),
}


def render_organ_cards(organ_assessments: Any) -> None:
    """Renders the 11 organ failure assessment cards in an ultra-clean responsive grid."""
    if hasattr(organ_assessments, "organ_assessments"):
        organ_assessments = organ_assessments.organ_assessments
    organ_assessments = organ_assessments or {}

    with ui.card().classes("w-full glass-card p-4 flex flex-col gap-3"):
        with ui.row().classes("w-full justify-between items-center border-b border-slate-700/60 pb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("health_and_safety", size="20px", color="cyan-4")
                ui.label("11 EVIDENCE-BASED PHYSIOLOGICAL ORGAN SYSTEMS").classes("text-xs font-bold text-slate-200 tracking-wider")
            
            failing_count = sum(1 for a in organ_assessments.values() if getattr(a, "grade", 0) >= 2)
            ui.badge(f"{failing_count} Failing Organs (Grade ≥ 2)", color="rose-900" if failing_count > 0 else "slate-800").classes(
                "text-xs font-mono"
            )

        # 3-column Grid for desktop, 2 for tablet, 1 for mobile
        with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1"):
            for organ_name, assessment in organ_assessments.items():
                grade = assessment.grade
                color, grade_label = GRADE_COLORS.get(grade, ("#32CD32", "Normal"))
                icon = ORGAN_ICONS.get(organ_name, "🏥")
                progress_pct = int((grade / 3.0) * 100)

                with ui.card().classes(
                    "bg-slate-900/85 p-3.5 rounded-xl border flex flex-col justify-between transition-all hover:border-slate-500"
                ).style(f"border-color: {color}44; border-left: 4px solid {color};"):
                    # Card Header
                    with ui.row().classes("w-full justify-between items-start"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(icon).classes("text-2xl")
                            with ui.column().classes("gap-0"):
                                ui.label(organ_name.upper()).classes("text-xs font-black text-slate-100 tracking-wider")
                                ui.label(assessment.guideline_reference).classes("text-[10px] text-slate-400 truncate max-w-[170px]")

                        ui.badge(f"G{grade}").style(
                            f"background-color: {color}22; color: {color}; border: 1px solid {color}66; font-weight: 800; font-size: 0.72rem; padding: 2px 7px;"
                        ).tooltip(grade_label)

                    # Progress Bar
                    ui.html(f"""
                        <div class="w-full bg-slate-800 rounded-full h-1.5 mt-2.5 overflow-hidden">
                            <div style="width: {max(progress_pct, 6)}%; height: 100%; background-color: {color}; border-radius: 9999px;"></div>
                        </div>
                    """)

                    # Clinical Description
                    ui.label(assessment.description).classes("text-xs text-slate-300 font-medium mt-2 leading-snug line-clamp-2")

                    # Evidence Bullets
                    if assessment.clinical_evidence:
                        with ui.column().classes("w-full gap-1 mt-2 bg-slate-950/60 p-2 rounded border border-slate-800/80"):
                            ui.label("EVIDENCE:").classes("text-[9px] font-bold text-slate-400 tracking-wider")
                            for ev in assessment.clinical_evidence[:2]:
                                ui.label(f"• {ev}").classes("text-[11px] text-slate-300 font-mono truncate")

                    # Suggested Action
                    if assessment.suggested_action:
                        ui.label(f"Action: {assessment.suggested_action}").classes(
                            "text-[10px] text-cyan-300 mt-2 font-mono truncate"
                        )
