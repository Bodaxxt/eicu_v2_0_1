"""
ICU Guard v5.0 — Pattern List Component
Renders the 16 critical syndrome evaluators with match confidence,
clinical criteria, differential diagnosis, and expandable details.
"""

from typing import List, Any
from nicegui import ui
from dashboard.utils.constants import TIER_COLORS, TIER_CRITICAL, TIER_HIGH


def render_pattern_list(patterns: Any) -> None:
    """Renders the 16 complex clinical syndrome matchers in expandable cards."""
    if hasattr(patterns, "patterns"):
        patterns = patterns.patterns
    patterns = patterns or []
    detected_patterns = [p for p in patterns if getattr(p, "detected", False)]
    negative_patterns = [p for p in patterns if not getattr(p, "detected", False)]

    with ui.card().classes("w-full glass-card p-4 flex flex-col gap-3"):
        with ui.row().classes("w-full justify-between items-center border-b border-slate-700/60 pb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("hub", size="20px", color="cyan-4")
                ui.label("16 CLINICAL SYNDROME PATTERN EVALUATORS").classes("text-xs font-bold text-slate-200 tracking-wider")

            ui.badge(
                f"{len(detected_patterns)} Syndromes Detected",
                color="rose-900" if detected_patterns else "emerald-950",
            ).classes("text-xs font-mono")

        # 1. Detected Patterns First (Urgent)
        if detected_patterns:
            ui.label("ACTIVE CLINICAL SYNDROMES (TRIGGERED):").classes("text-[10px] font-bold text-rose-400 tracking-wider")
            for p in detected_patterns:
                conf = p.confidence
                color = TIER_COLORS[TIER_CRITICAL] if conf == "HIGH" else TIER_COLORS[TIER_HIGH]

                recommendation = getattr(p, "clinical_recommendation", "") or getattr(p, "clinical_rationale", "")
                criteria = getattr(p, "diagnostic_criteria_met", None)
                if criteria is None:
                    criteria = getattr(p, "criteria_met", [])
                contributing = getattr(p, "contributing_organs", [])

                with ui.expansion(f"🚨 {p.pattern_name.upper()} — [{conf} CONFIDENCE]").classes(
                    "w-full bg-slate-900/90 rounded-lg border border-slate-700 text-xs text-slate-100"
                ).style(f"border-left: 4px solid {color};"):
                    with ui.column().classes("p-3 gap-2 bg-slate-950/60 rounded"):
                        if recommendation:
                            ui.label(f"Clinical Guidance: {recommendation}").classes("text-xs text-slate-300")
                        
                        if criteria:
                            ui.label("Diagnostic Criteria Satisfied:").classes("text-[10px] font-bold text-slate-400")
                            for c in criteria:
                                ui.label(f"• {c}").classes("text-[11px] text-slate-300 font-mono")

                        if contributing:
                            ui.label(f"Contributing Organ Systems: {', '.join(contributing)}").classes(
                                "text-[11px] text-cyan-300 font-mono"
                            )

        # 2. Negative / Cleared Patterns
        ui.label("CLEARED SYNDROME PATTERNS (NEGATIVE):").classes("text-[10px] font-bold text-slate-400 tracking-wider mt-2")
        with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2"):
            for p in negative_patterns:
                with ui.card().classes(
                    "bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80 flex flex-row items-center justify-between"
                ):
                    ui.label(p.pattern_name).classes("text-[11px] text-slate-400 truncate max-w-[170px]")
                    ui.icon("check_circle", size="16px", color="emerald-500").tooltip("Pattern criteria not met (Negative)")
