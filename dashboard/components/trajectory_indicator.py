"""
trajectory_indicator.py — Visual Clinical Acuity Trajectory Component
======================================================================
Renders prominent velocity badges, rate of change (%/hr), time-to-critical
countdowns, and model confidence indicators.
"""

from __future__ import annotations

from typing import Optional
from nicegui import ui
from severity_agent.hl7.trajectory import TrajectoryResult


class TrajectoryIndicator:
    """Component rendering trajectory status with velocity metrics."""

    TRAJECTORY_STYLES = {
        "RAPID_DETERIORATION": {
            "label": "RAPID DETERIORATION",
            "icon": "bolt",
            "color": "rose-600",
            "bg": "bg-rose-950/70",
            "border": "border-rose-500",
            "text": "text-rose-400",
        },
        "SLOW_DETERIORATION": {
            "label": "SLOW DETERIORATION",
            "icon": "trending_up",
            "color": "amber-500",
            "bg": "bg-amber-950/60",
            "border": "border-amber-500",
            "text": "text-amber-400",
        },
        "IMPROVING": {
            "label": "IMPROVING / STABILIZING",
            "icon": "trending_down",
            "color": "emerald-500",
            "bg": "bg-emerald-950/60",
            "border": "border-emerald-500",
            "text": "text-emerald-400",
        },
        "STABLE": {
            "label": "PHYSIOLOGICALLY STABLE",
            "icon": "verified",
            "color": "cyan-500",
            "bg": "bg-cyan-950/40",
            "border": "border-cyan-500/50",
            "text": "text-cyan-400",
        },
    }

    def __init__(self):
        self.container = None
        self.badge = None
        self.rate_label = None
        self.countdown_label = None
        self.summary_label = None
        self.confidence_label = None

    def render(self, initial_trajectory: Optional[TrajectoryResult] = None) -> None:
        """Constructs the UI card for the trajectory indicator."""
        style = self.TRAJECTORY_STYLES.get("STABLE")

        with ui.card().classes("glass-card p-4 rounded-xl border border-slate-800 shadow-lg w-full") as self.container:
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("speed", size="22px", color="cyan-4")
                    ui.label("PHYSIOLOGICAL TRAJECTORY").classes("text-xs font-bold text-slate-400 tracking-wider font-mono")

                self.confidence_label = ui.badge("Conf: 85%", color="slate-800").classes("text-xs font-mono text-slate-300 border border-slate-700")

            with ui.row().classes("w-full items-center justify-between mt-2 flex-wrap gap-3"):
                with ui.row().classes(f"items-center gap-2 px-3 py-1.5 rounded-lg border {style['border']} {style['bg']}") as self.badge_box:
                    self.icon = ui.icon(style["icon"], size="20px", color="cyan-4")
                    self.type_label = ui.label(style["label"]).classes(f"text-sm font-extrabold font-mono {style['text']}")

                with ui.row().classes("items-center gap-4"):
                    with ui.column().classes("gap-0 items-end"):
                        ui.label("VELOCITY (Δ/hr)").classes("text-[10px] text-slate-400 font-mono")
                        self.rate_label = ui.label("+0.0%/hr").classes("text-sm font-bold text-slate-200 font-mono")

                    with ui.column().classes("gap-0 items-end"):
                        ui.label("TIME TO CRITICAL").classes("text-[10px] text-slate-400 font-mono")
                        self.countdown_label = ui.label("Nominal").classes("text-sm font-bold text-emerald-400 font-mono")

            self.summary_label = ui.label("Monitoring physiological trajectory continuously...").classes(
                "text-xs text-slate-400 mt-2 font-mono italic"
            )

        if initial_trajectory:
            self.update(initial_trajectory)

    def update(self, traj: TrajectoryResult) -> None:
        """Updates indicator elements with new velocity calculation."""
        if not self.container:
            return

        style = self.TRAJECTORY_STYLES.get(traj.trajectory_type, self.TRAJECTORY_STYLES["STABLE"])

        # Update badge
        self.badge_box.classes(remove="border-rose-500 bg-rose-950/70 border-amber-500 bg-amber-950/60 border-emerald-500 bg-emerald-950/60 border-cyan-500/50 bg-cyan-950/40")
        self.badge_box.classes(add=f"{style['border']} {style['bg']}")

        self.icon.name = style["icon"]
        self.type_label.text = style["label"]
        self.type_label.classes(remove="text-rose-400 text-amber-400 text-emerald-400 text-cyan-400")
        self.type_label.classes(add=style["text"])

        # Rates
        pct_rate = traj.rate_of_change_per_hour * 100.0
        sign = "+" if pct_rate > 0 else ""
        self.rate_label.text = f"{sign}{pct_rate:.1f}%/hr"
        if pct_rate > 8.0:
            self.rate_label.classes(remove="text-slate-200 text-emerald-400 text-amber-400", add="text-rose-400")
        elif pct_rate > 2.0:
            self.rate_label.classes(remove="text-slate-200 text-emerald-400 text-rose-400", add="text-amber-400")
        elif pct_rate < -2.0:
            self.rate_label.classes(remove="text-slate-200 text-rose-400 text-amber-400", add="text-emerald-400")
        else:
            self.rate_label.classes(remove="text-rose-400 text-amber-400 text-emerald-400", add="text-slate-200")

        # Countdown
        if traj.time_to_critical_minutes is not None:
            mins = int(round(traj.time_to_critical_minutes))
            if mins <= 60:
                self.countdown_label.text = f"~{mins} mins ⚠️"
                self.countdown_label.classes(remove="text-emerald-400 text-amber-400", add="text-rose-400")
            else:
                hours = mins // 60
                rem_mins = mins % 60
                self.countdown_label.text = f"~{hours}h {rem_mins}m"
                self.countdown_label.classes(remove="text-emerald-400 text-rose-400", add="text-amber-400")
        else:
            self.countdown_label.text = "Nominal"
            self.countdown_label.classes(remove="text-rose-400 text-amber-400", add="text-emerald-400")

        # Confidence
        self.confidence_label.text = f"Conf: {int(traj.confidence * 100)}%"
        self.summary_label.text = traj.summary
