"""
pattern_evolution.py — Real-Time Syndrome & Clinical Pattern Evolution Component
================================================================================
Displays active detected clinical patterns/syndromes from the 16 ICU Guard
detectors, showing confidence scores, urgency classifications, and recommendations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from nicegui import ui


class PatternEvolution:
    """Component rendering evolving clinical syndromes."""

    def __init__(self):
        self.container = None
        self.count_badge = None
        self.list_container = None

    def render(self, patterns: Optional[List[Dict[str, Any]]] = None) -> None:
        """Constructs the pattern evolution card container."""
        with ui.card().classes("glass-card p-4 rounded-xl border border-slate-800 shadow-lg w-full flex flex-col h-full"):
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-slate-800"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("biotech", size="20px", color="cyan-4")
                    ui.label("ACTIVE CLINICAL SYNDROMES").classes("text-xs font-bold text-slate-300 font-mono tracking-wider")

                self.count_badge = ui.badge("0 Patterns", color="slate-800").classes("text-xs font-mono text-slate-300 border border-slate-700")

            self.list_container = ui.column().classes("w-full gap-2.5 mt-3 overflow-y-auto max-h-64 pr-1")
            self._render_items(patterns or [])

    def update(self, patterns: List[Dict[str, Any]]) -> None:
        """Updates the list of detected clinical patterns."""
        if not self.list_container:
            return
        active = [p for p in patterns if p.get("detected", True)]
        self.count_badge.text = f"{len(active)} Syndrome{'s' if len(active) != 1 else ''}"
        if len(active) > 0:
            self.count_badge.classes(remove="text-slate-300 border-slate-700", add="text-cyan-300 border-cyan-500 bg-cyan-950/80")
        self.list_container.clear()
        with self.list_container:
            self._render_items(active)

    def _render_items(self, patterns: List[Dict[str, Any]]) -> None:
        if not patterns:
            with ui.column().classes("w-full py-6 items-center justify-center text-slate-500 gap-2"):
                ui.icon("health_and_safety", size="28px", color="cyan-500")
                ui.label("No Acute Syndromes Detected").classes("text-xs font-mono text-slate-400")
            return

        for p in patterns:
            p_name = p.get("name", "Clinical Syndrome")
            conf = float(p.get("confidence", 0.85)) * 100.0
            urgency = p.get("urgency", "TIER 2 (HIGH)")
            rec = p.get("recommendation", "Continue intensive hemodynamic monitoring.")

            is_crit = "TIER 1" in str(urgency).upper() or "CRIT" in str(urgency).upper()
            border_cls = "border-rose-500 bg-rose-950/40" if is_crit else "border-cyan-500/60 bg-cyan-950/30"
            badge_color = "rose-600" if is_crit else "cyan-700"

            with ui.card().classes(f"w-full p-2.5 rounded-lg border {border_cls} shadow-sm"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(p_name).classes("text-xs font-bold text-slate-100 font-mono")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.badge(f"{conf:.0f}% Conf", color="slate-900").classes("text-[10px] font-mono text-cyan-300 border border-slate-700")
                        ui.badge(urgency, color=badge_color).classes("text-[10px] font-mono text-white font-bold")

                ui.label(rec).classes("text-[11px] text-slate-300 font-mono mt-1 italic")
