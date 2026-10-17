"""
ICU Guard v5.0 — Live Telemetry Timeline Component
Displays streaming line-by-line physiological events with auto-scroll,
severity color coding, and telemetry log export.
"""

from typing import List, Dict, Any
from nicegui import ui
from dashboard.streaming.data_streamer import StreamFrame
from dashboard.streaming.live_analyzer import LiveAnalysisResult
from dashboard.utils.constants import TIER_COLORS


class TimelineFeed:
    """Manages the chronological streaming feed of vital telemetry events."""

    def __init__(self, max_entries: int = 200):
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []
        self._build_timeline()

    def _build_timeline(self) -> None:
        """Constructs the scrollable terminal-style timeline container."""
        with ui.card().classes("w-full glass-card p-4 flex flex-col gap-2 border border-slate-700/60"):
            # Header
            with ui.row().classes("w-full justify-between items-center border-b border-slate-700/60 pb-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("history", size="20px", color="cyan-4")
                    ui.label("TIMELINE — LIVE TELEMETRY FEED").classes("text-xs font-bold text-slate-200 tracking-wider")
                self.count_badge = ui.badge("0 events", color="slate-800").classes("text-xs text-slate-400 font-mono")

            # Scrollable Feed Container
            self.feed_scroll = ui.scroll_area().classes("w-full h-44 bg-slate-950/80 rounded-lg p-3 border border-slate-800 font-mono text-xs")
            with self.feed_scroll:
                self.feed_column = ui.column().classes("w-full gap-1.5")
                with self.feed_column:
                    ui.label("Connecting to bedside patient monitor... awaiting first telemetry packet.").classes(
                        "text-slate-500 italic text-[11px]"
                    )

    def add_entry(self, frame: StreamFrame, analysis: LiveAnalysisResult) -> None:
        """Appends a new line-by-line telemetry event and auto-scrolls."""
        v = frame.vitals
        tier = analysis.current_tier
        tier_color = analysis.tier_color

        hr = f"{v.get('hr', 0):.0f}"
        sbp = f"{v.get('sbp', 0):.0f}"
        mbp = f"{v.get('map', 0):.0f}"
        rr = f"{v.get('rr', 0):.0f}"
        temp = f"{v.get('temp', 0):.1f}"
        sao2 = f"{v.get('sao2', 0):.0f}"
        gcs = f"{v.get('gcs', 0):.0f}"

        # If it's the first real event, clear the placeholder
        if len(self.entries) == 0:
            self.feed_column.clear()

        self.entries.append({
            "tick": frame.tick,
            "time": frame.timestamp_str,
            "tier": tier,
        })

        with self.feed_column:
            with ui.row().classes(
                "w-full items-center justify-between py-1 px-2.5 rounded bg-slate-900/60 hover:bg-slate-800/80 transition-colors"
            ).style(f"border-left: 3px solid {tier_color};"):
                with ui.row().classes("items-center gap-3 flex-wrap"):
                    ui.label(f"[{frame.timestamp_str}]").classes("text-cyan-400 font-bold")
                    ui.label(f"HR: {hr} bpm").classes("text-slate-200")
                    ui.label("|").classes("text-slate-600")
                    ui.label(f"BP: {sbp}/{mbp} mmHg").classes("text-slate-200")
                    ui.label("|").classes("text-slate-600")
                    ui.label(f"RR: {rr} /min").classes("text-slate-200")
                    ui.label("|").classes("text-slate-600")
                    ui.label(f"Temp: {temp}°C").classes("text-slate-200")
                    ui.label("|").classes("text-slate-600")
                    ui.label(f"SaO2: {sao2}%").classes("text-slate-200")
                    ui.label("|").classes("text-slate-600")
                    ui.label(f"GCS: {gcs}").classes("text-slate-200")

                ui.badge(tier).style(
                    f"color: {tier_color}; background-color: {tier_color}22; border: 1px solid {tier_color}44; font-size: 0.65rem; padding: 2px 6px;"
                )

        # Update counter and scroll to bottom
        self.count_badge.text = f"{len(self.entries)} events"
        self.feed_scroll.scroll_to(percent=1.0)
