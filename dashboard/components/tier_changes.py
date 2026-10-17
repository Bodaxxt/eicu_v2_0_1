"""
tier_changes.py — Longitudinal Tier Escalation Events List Component
====================================================================
Displays all acute tier transitions (e.g. STABLE ➔ MODERATE ➔ HIGH ➔ CRITICAL)
with exact timestamps, trigger reasons, and non-downgrading compliance.
"""

from __future__ import annotations

from typing import List, Optional
from nicegui import ui
from severity_agent.hl7.tier_detector import TierChangeEvent


class TierChangesList:
    """Component listing recorded tier transition events."""

    TIER_COLORS = {
        "CRITICAL": {"bg": "bg-rose-950/80", "border": "border-rose-500", "text": "text-rose-400", "badge": "rose-600"},
        "HIGH": {"bg": "bg-orange-950/70", "border": "border-orange-500", "text": "text-orange-400", "badge": "orange-500"},
        "MODERATE": {"bg": "bg-amber-950/60", "border": "border-amber-500", "text": "text-amber-400", "badge": "amber-500"},
        "STABLE": {"bg": "bg-emerald-950/60", "border": "border-emerald-500", "text": "text-emerald-400", "badge": "emerald-600"},
    }

    def __init__(self):
        self.container = None
        self.count_badge = None

    def render(self, events: Optional[List[TierChangeEvent]] = None) -> None:
        """Constructs the tier changes card container."""
        with ui.card().classes("glass-card p-4 rounded-xl border border-slate-800 shadow-lg w-full flex flex-col h-full"):
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-slate-800"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("notification_important", size="20px", color="rose-400")
                    ui.label("ACUITY TIER TRANSITIONS").classes("text-xs font-bold text-slate-300 font-mono tracking-wider")

                self.count_badge = ui.badge("0 Changes", color="slate-800").classes("text-xs font-mono text-slate-300 border border-slate-700")

            self.list_container = ui.column().classes("w-full gap-2.5 mt-3 overflow-y-auto max-h-64 pr-1")
            self._render_items(events or [])

    def update(self, events: List[TierChangeEvent]) -> None:
        """Updates the list of tier change cards."""
        if not self.list_container:
            return
        self.count_badge.text = f"{len(events)} Escalation{'s' if len(events) != 1 else ''}"
        if len(events) > 0:
            self.count_badge.classes(remove="text-slate-300 border-slate-700", add="text-rose-300 border-rose-500 bg-rose-950/80")
        self.list_container.clear()
        with self.list_container:
            self._render_items(events)

    def _render_items(self, events: List[TierChangeEvent]) -> None:
        if not events:
            with ui.column().classes("w-full py-6 items-center justify-center text-slate-500 gap-2"):
                ui.icon("check_circle", size="28px", color="emerald-400")
                ui.label("No Acuity Escalations Yet (STABLE)").classes("text-xs font-mono text-slate-400")
            return

        for evt in events:
            new_style = self.TIER_COLORS.get(evt.new_tier, self.TIER_COLORS["CRITICAL"])
            prev_style = self.TIER_COLORS.get(evt.previous_tier, self.TIER_COLORS["STABLE"])

            with ui.card().classes(f"w-full p-2.5 rounded-lg border {new_style['border']} {new_style['bg']} shadow-sm"):
                with ui.row().classes("w-full items-center justify-between"):
                    # Time & Transition Arrow
                    with ui.row().classes("items-center gap-1.5 font-mono text-xs font-bold"):
                        ui.badge(evt.sim_time_str, color="slate-900").classes("text-cyan-300 border border-slate-700 text-[11px]")
                        ui.label(evt.previous_tier).classes(f"text-[11px] {prev_style['text']}")
                        ui.icon("arrow_forward", size="14px", color="slate-400")
                        ui.label(evt.new_tier).classes(f"text-[11px] font-extrabold {new_style['text']}")

                    ui.badge("NON-DOWNGRADING", color="slate-900").classes("text-[9px] font-mono text-slate-400 border border-slate-700")

                # Reason & Probabilities
                ui.label(evt.trigger_reason).classes("text-xs text-slate-300 font-mono mt-1")
                with ui.row().classes("items-center gap-3 mt-1 text-[10px] text-slate-400 font-mono"):
                    ui.label(f"Det: {evt.deterioration_risk*100:.1f}%")
                    ui.label(f"Mort: {evt.mortality_risk*100:.1f}%")
                    if evt.active_patterns:
                        ui.label(f"Pattern: {evt.active_patterns[0]}").classes("text-rose-300 italic")
