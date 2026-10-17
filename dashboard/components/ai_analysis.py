"""
ICU Guard v5.0 — Real-Time AI Clinical Analysis Component
Renders deterministic acuity triage tier, trajectory progression,
active organ failure grades, syndrome pattern matches, and trend velocities.
"""

from typing import Dict, Any, List
from nicegui import ui
from dashboard.streaming.live_analyzer import LiveAnalysisResult, TrendItem
from dashboard.utils.constants import TIER_COLORS


class AIAnalysisPanel:
    """Manages the real-time AI reasoning and diagnostic visualization card."""

    def __init__(self):
        self._build_panel()

    def _build_panel(self) -> None:
        """Constructs the glassmorphic AI analysis interface."""
        with ui.card().classes(
            "w-full glass-card p-5 flex flex-col gap-4 border border-cyan-500/30 bg-gradient-to-b from-slate-900 to-slate-800"
        ):
            # Header
            with ui.row().classes("w-full justify-between items-center border-b border-slate-700/60 pb-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("psychology", size="24px", color="cyan-4")
                    ui.label("REAL-TIME CLINICAL REASONING").classes("text-xs font-bold text-slate-200 tracking-wider")
                self.tier_badge = ui.badge("STABLE", color="transparent").style(
                    "border: 1px solid #32CD32; color: #32CD32; background-color: rgba(50,205,50,0.15); font-weight: bold; font-size: 0.8rem; padding: 4px 10px;"
                )

            # Acuity & Trajectory Row
            with ui.row().classes("w-full grid grid-cols-2 gap-3"):
                with ui.card().classes("bg-slate-900/80 p-3 rounded-lg border border-slate-800"):
                    ui.label("PHYSIOLOGICAL TRAJECTORY").classes("text-[10px] text-slate-400 font-bold tracking-wider")
                    self.trajectory_label = ui.label("STABLE").classes("text-sm font-extrabold text-emerald-400 mt-1")

                with ui.card().classes("bg-slate-900/80 p-3 rounded-lg border border-slate-800"):
                    ui.label("COMPOSITE SEVERITY INDEX").classes("text-[10px] text-slate-400 font-bold tracking-wider")
                    self.severity_score_label = ui.label("0.5 / 10.0").classes("text-sm font-extrabold text-slate-100 mt-1")

            # Active Clinical Syndrome Patterns
            with ui.column().classes("w-full gap-1.5"):
                ui.label("ACTIVE SYNDROME PATTERNS:").classes("text-[10px] text-slate-400 font-bold tracking-wider")
                self.patterns_container = ui.row().classes("w-full gap-2 flex-wrap min-h-[32px] items-center")
                with self.patterns_container:
                    ui.label("No acute clinical syndromes detected.").classes("text-xs text-slate-500 italic")

            # Top Physiological Trends (Velocities)
            with ui.column().classes("w-full gap-1.5"):
                ui.label("DYNAMIC TREND VELOCITIES (TOP 3):").classes("text-[10px] text-slate-400 font-bold tracking-wider")
                self.trends_container = ui.row().classes("w-full grid grid-cols-3 gap-2")
                with self.trends_container:
                    for _ in range(3):
                        with ui.card().classes("bg-slate-900/60 p-2 rounded border border-slate-800"):
                            ui.label("—").classes("text-[10px] text-slate-400")
                            ui.label("Stable").classes("text-xs font-bold text-slate-300")

            # Recommended Action Protocol
            with ui.card().classes("w-full bg-slate-900/90 p-3 rounded-lg border border-slate-700/80 mt-1"):
                ui.label("AUTONOMOUS PROTOCOL DIRECTIVE:").classes("text-[10px] font-bold text-amber-400 tracking-wider")
                self.action_label = ui.label(
                    "Maintain standard ICU surveillance protocol; continue scheduled telemetry and routine checks."
                ).classes("text-xs text-slate-300 mt-1 leading-relaxed")

    def update(self, result: LiveAnalysisResult) -> None:
        """Updates all reasoning cards with the latest inference tick."""
        # 1. Tier Badge
        tier = result.current_tier
        color = result.tier_color
        self.tier_badge.text = f"{tier}"
        self.tier_badge.style(
            f"border: 1px solid {color}; color: {color}; background-color: {color}22; font-weight: bold; font-size: 0.8rem; padding: 4px 10px;"
        )

        # 2. Trajectory
        traj = result.trajectory
        traj_color = "#DC143C" if "RAPID" in traj else "#FF8C00" if "SLOW" in traj else "#32CD32"
        traj_display = traj.replace("_", " ")
        self.trajectory_label.text = traj_display
        self.trajectory_label.style(f"color: {traj_color};")

        # 3. Severity Score
        self.severity_score_label.text = f"{result.overall_score:.1f} / 10.0"

        # 4. Patterns Container
        self.patterns_container.clear()
        with self.patterns_container:
            if result.detected_patterns:
                for p in result.detected_patterns:
                    conf_color = TIER_COLORS.get("CRITICAL" if p.confidence == "HIGH" else "HIGH", "#FF8C00")
                    ui.badge(f"🚨 {p.pattern_name} ({p.confidence})").style(
                        f"border: 1px solid {conf_color}; color: {conf_color}; background-color: {conf_color}22; font-weight: bold; font-size: 0.72rem; padding: 3px 8px;"
                    )
            else:
                ui.label("✅ All 16 clinical syndrome patterns clear.").classes("text-xs text-emerald-400")

        # 5. Trends Container
        self.trends_container.clear()
        with self.trends_container:
            for item in result.top_trends:
                with ui.card().classes("bg-slate-900/80 p-2 rounded border border-slate-800 justify-between"):
                    ui.label(item.metric).classes("text-[10px] text-slate-400 truncate")
                    with ui.row().classes("items-center gap-1 mt-0.5"):
                        ui.label(item.arrow).classes("text-xs")
                        ui.label(item.delta_text).classes(
                            "text-xs font-bold " + ("text-rose-400" if item.is_worsening else "text-slate-200")
                        )

        # 6. Action Directive
        self.action_label.text = result.recommended_action
