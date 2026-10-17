"""
ICU Guard v5.0 — Triage Header Component
Displays clinical acuity tier (STABLE, MODERATE, HIGH, CRITICAL), safety override
audit alerts, patient demographics, and navigation action triggers.
"""

from typing import Dict, Any, Callable, Optional
from nicegui import ui
from dashboard.utils.constants import TIER_COLORS, TIER_CRITICAL, TIER_HIGH, TIER_MODERATE, TIER_STABLE


TIER_NUMBERS = {
    TIER_STABLE: 0,
    TIER_MODERATE: 1,
    TIER_HIGH: 2,
    TIER_CRITICAL: 3,
}


def render_triage_header(
    patient: Any,
    assessment: Any = None,
    on_sbar: Optional[Callable[[], None]] = None,
    on_chat: Optional[Callable[[], None]] = None,
    on_pdf: Optional[Callable[[], None]] = None,
) -> None:
    """Renders the comprehensive clinical triage header banner."""
    # Defensive handling for swapped arguments or direct severity object
    if not isinstance(patient, dict) and hasattr(patient, "severity"):
        assessment, patient = patient, assessment
    elif isinstance(assessment, dict) and not isinstance(patient, dict):
        assessment, patient = patient, assessment

    patient_dict = patient if isinstance(patient, dict) else {}
    sev = getattr(assessment, "severity", assessment)
    final_tier = getattr(sev, "final_tier", "STABLE")
    tier_color = TIER_COLORS.get(final_tier, "#32CD32")
    tier_num = TIER_NUMBERS.get(final_tier, 0)
    overall_score = getattr(sev, "overall_score", 0.0)

    cb_sbar = on_sbar or (lambda: None)
    cb_chat = on_chat or (lambda: None)
    cb_pdf = on_pdf or (lambda: None)

    with ui.card().classes(
        "w-full glass-card-elevated p-6 flex flex-col gap-4 border"
    ).style(f"border-color: {tier_color}88; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);"):
        # Top Bar: Patient ID + Actions
        with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
            with ui.row().classes("items-center gap-4"):
                pid = patient_dict.get('id', 'N/A')
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to(f"/live_monitor?patient_id={pid}")).props(
                    "flat round color=cyan-4"
                ).tooltip("Return to Live Bedside Monitor")

                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"PATIENT #{pid}").classes("text-2xl font-black text-white font-mono tracking-wide")
                        ui.badge(f"TIER {tier_num} • {final_tier}").style(
                            f"border: 1px solid {tier_color}; color: {tier_color}; background-color: {tier_color}22; font-weight: 800; font-size: 0.85rem; padding: 4px 12px; letter-spacing: 0.05em;"
                        )
                    ui.label(
                        f"Age: {patient_dict.get('age', 'N/A')} • Gender: {patient_dict.get('gender', 'N/A')} • APACHE IV: {patient_dict.get('apache', 'N/A')} • Severity Index: {overall_score:.1f}/10"
                    ).classes("text-xs text-slate-400 font-mono")

            # Quick Action Buttons
            with ui.row().classes("items-center gap-2 flex-wrap"):
                ui.button("SBAR Handoff", icon="description", on_click=cb_sbar).props("outline color=cyan-3").classes(
                    "font-bold text-xs"
                )
                ui.button("Bedside Copilot", icon="smart_toy", on_click=cb_chat).props("outline color=cyan-3").classes(
                    "font-bold text-xs"
                )
                ui.button("Export PDF Report", icon="picture_as_pdf", on_click=cb_pdf).props("unelevated color=primary").classes(
                    "font-bold text-xs px-4"
                )

        # Safety Override & Escalation Audit Notice
        if sev.escalation_occurred:
            with ui.row().classes("w-full items-center gap-3 p-3 rounded-lg bg-rose-950/40 border border-rose-600/50"):
                ui.icon("emergency", size="24px", color="rose-400")
                with ui.column().classes("gap-0 flex-1"):
                    ui.label("CLINICAL SAFETY ARBITRATION OVERRIDE TRIGGERED").classes(
                        "text-xs font-bold text-rose-300 tracking-wider"
                    )
                    reasons = " | ".join(sev.escalation_reasons) if sev.escalation_reasons else "Non-downgrading critical organ failure override."
                    ui.label(f"ML Baseline: {sev.ml_base_tier} → Escalated to: {final_tier} ({reasons})").classes(
                        "text-xs text-rose-200"
                    )
        elif sev.active_red_flags:
            with ui.row().classes("w-full items-center gap-3 p-3 rounded-lg bg-amber-950/40 border border-amber-600/50"):
                ui.icon("warning", size="24px", color="amber-400")
                ui.label(f"Active Physiological Red Flags: {', '.join(sev.active_red_flags)}").classes(
                    "text-xs text-amber-200 font-medium"
                )
        else:
            with ui.row().classes("w-full items-center gap-2 p-2 rounded bg-emerald-950/30 border border-emerald-600/30"):
                ui.icon("check_circle", size="18px", color="emerald-400")
                ui.label("Safety Validation Coherent: ML probabilities and organ detector grades in physiological equilibrium.").classes(
                    "text-xs text-emerald-300 font-mono"
                )
