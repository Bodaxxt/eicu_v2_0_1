"""
prediction_timeline.py — Continuous Bedside Prediction Event Feed Component
============================================================================
Renders chronological time-series feed of continuous 5-minute prediction ticks,
acute tier changes, pattern discoveries, and physiological milestones.
"""

from __future__ import annotations

from typing import List, Optional
from nicegui import ui
from severity_agent.hl7.live_timeline import TimelineEvent


class PredictionTimelineFeed:
    """Component rendering chronological live event stream."""

    SEV_STYLES = {
        "CRITICAL": {"border": "border-rose-500", "bg": "bg-rose-950/40", "badge": "rose-600", "text": "text-rose-400"},
        "WARNING": {"border": "border-amber-500", "bg": "bg-amber-950/30", "badge": "amber-600", "text": "text-amber-400"},
        "SUCCESS": {"border": "border-emerald-500", "bg": "bg-emerald-950/30", "badge": "emerald-600", "text": "text-emerald-400"},
        "INFO": {"border": "border-slate-800", "bg": "bg-slate-900/60", "badge": "slate-800", "text": "text-cyan-400"},
    }

    def __init__(self, max_display: int = 50):
        self.max_display = max_display
        self.container = None
        self.count_badge = None
        self.list_container = None

    def render(self, events: Optional[List[TimelineEvent]] = None) -> None:
        """Constructs timeline card container."""
        with ui.card().classes("glass-card p-4 rounded-xl border border-slate-800 shadow-lg w-full flex flex-col h-full"):
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-slate-800"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("history_toggle_drop_down", size="22px", color="cyan-4")
                    ui.label("CONTINUOUS EVENT STREAM").classes("text-xs font-bold text-slate-300 font-mono tracking-wider")

                self.count_badge = ui.badge("0 Events", color="slate-800").classes("text-xs font-mono text-slate-300 border border-slate-700")

            self.list_container = ui.column().classes("w-full gap-2 mt-3 overflow-y-auto max-h-72 pr-1")
            self._render_items(events or [])

    def update(self, events: List[TimelineEvent]) -> None:
        """Updates event items with newest on top."""
        if not self.list_container:
            return
        self.count_badge.text = f"{len(events)} Events"
        self.list_container.clear()
        with self.list_container:
            self._render_items(events)

    def _render_items(self, events: List[TimelineEvent]) -> None:
        if not events:
            with ui.column().classes("w-full py-6 items-center justify-center text-slate-500 gap-2"):
                ui.icon("schedule", size="26px", color="slate-500")
                ui.label("Waiting for continuous scheduler ticks...").classes("text-xs font-mono text-slate-400")
            return

        # Show newest events first
        for evt in reversed(events[-self.max_display:]):
            st = self.SEV_STYLES.get(evt.severity, self.SEV_STYLES["INFO"])

            with ui.card().classes(f"w-full p-2 rounded-lg border {st['border']} {st['bg']} shadow-xs"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.row().classes("items-center gap-2"):
                        ui.badge(evt.sim_time_str, color="slate-950").classes("text-[10px] font-mono text-cyan-300 border border-slate-800")
                        ui.label(evt.title).classes(f"text-xs font-bold font-mono {st['text']}")

                    ui.badge(evt.event_type, color=st["badge"]).classes("text-[9px] font-mono text-white")

                ui.label(evt.description).classes("text-[11px] text-slate-300 font-mono mt-0.5")
