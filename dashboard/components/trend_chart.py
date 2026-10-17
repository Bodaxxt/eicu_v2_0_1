"""
trend_chart.py — Interactive Longitudinal Clinical Risk Trend Chart (Plotly)
=============================================================================
Renders continuous multi-hour risk probability trends (Mortality, Deterioration,
Severe Acuity) with acuity threshold bands and tier transition annotations.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from nicegui import ui
import plotly.graph_objects as go
from severity_agent.hl7.history import PredictionRecord
from severity_agent.hl7.tier_detector import TierChangeEvent


class TrendChart:
    """Component rendering Plotly multi-hour continuous risk curves."""

    def __init__(self):
        self.plot_element = None

    def render(self, history: Optional[List[PredictionRecord]] = None, tier_changes: Optional[List[TierChangeEvent]] = None) -> None:
        """Constructs the Plotly trend chart within a glass card container."""
        fig = self._build_figure(history or [], tier_changes or [])
        with ui.card().classes("glass-card p-4 rounded-xl border border-slate-800 shadow-xl w-full"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("show_chart", size="22px", color="cyan-4")
                    ui.label("CONTINUOUS MULTI-TARGET RISK TRAJECTORY (10-HOUR WINDOW)").classes(
                        "text-xs font-bold text-slate-300 font-mono tracking-wider"
                    )

                with ui.row().classes("items-center gap-4 text-xs font-mono"):
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html('<div class="w-3 h-3 rounded-full bg-rose-500"></div>')
                        ui.label("Deterioration").classes("text-slate-300 text-[11px]")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html('<div class="w-3 h-3 rounded-full bg-amber-400"></div>')
                        ui.label("Mortality").classes("text-slate-300 text-[11px]")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html('<div class="w-3 h-3 rounded-full bg-cyan-400"></div>')
                        ui.label("Severe Acuity").classes("text-slate-300 text-[11px]")

            self.plot_element = ui.plotly(fig).classes("w-full h-80")

    def update(self, history: List[PredictionRecord], tier_changes: Optional[List[TierChangeEvent]] = None) -> None:
        """Updates the Plotly figure with new longitudinal points."""
        if not self.plot_element:
            return
        fig = self._build_figure(history, tier_changes or [])
        self.plot_element.update_figure(fig)

    def _build_figure(self, history: List[PredictionRecord], tier_changes: List[TierChangeEvent]) -> go.Figure:
        """Builds dark-mode styled Plotly figure."""
        fig = go.Figure()

        if not history:
            x_vals = ["00:00"]
            y_det = [0.15]
            y_mort = [0.08]
            y_sev = [0.12]
        else:
            x_vals = [r.sim_time_str for r in history]
            y_det = [r.deterioration_risk * 100.0 for r in history]
            y_mort = [r.mortality_risk * 100.0 for r in history]
            y_sev = [r.severe_risk * 100.0 for r in history]

        # Acuity Threshold Bands (Horizontal Rectangles / Lines)
        fig.add_hrect(
            y0=70, y1=100,
            fillcolor="rgba(244, 63, 94, 0.08)", line_width=0,
            annotation_text="CRITICAL (TIER 1)", annotation_position="top right",
            annotation_font=dict(size=10, color="rgba(244, 63, 94, 0.7)", family="monospace"),
        )
        fig.add_hrect(
            y0=40, y1=70,
            fillcolor="rgba(245, 158, 11, 0.06)", line_width=0,
            annotation_text="HIGH ACUITY (TIER 2)", annotation_position="top right",
            annotation_font=dict(size=10, color="rgba(245, 158, 11, 0.7)", family="monospace"),
        )
        fig.add_hrect(
            y0=20, y1=40,
            fillcolor="rgba(251, 191, 36, 0.04)", line_width=0,
            annotation_text="MODERATE (TIER 3)", annotation_position="top right",
            annotation_font=dict(size=10, color="rgba(251, 191, 36, 0.6)", family="monospace"),
        )

        # Deterioration Curve
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_det,
            mode="lines+markers" if len(x_vals) < 30 else "lines",
            name="Deterioration Risk",
            line=dict(color="#f43f5e", width=3, shape="spline"),
            marker=dict(size=4, color="#f43f5e"),
            hovertemplate="Time: %{x}<br>Deterioration: %{y:.1f}%<extra></extra>",
        ))

        # Severe Acuity Curve
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_sev,
            mode="lines+markers" if len(x_vals) < 30 else "lines",
            name="Severe Acuity",
            line=dict(color="#22d3ee", width=2.5, shape="spline", dash="dot"),
            marker=dict(size=3, color="#22d3ee"),
            hovertemplate="Time: %{x}<br>Severe Risk: %{y:.1f}%<extra></extra>",
        ))

        # Mortality Curve
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_mort,
            mode="lines+markers" if len(x_vals) < 30 else "lines",
            name="Mortality Risk",
            line=dict(color="#fbbf24", width=2.5, shape="spline"),
            marker=dict(size=3, color="#fbbf24"),
            hovertemplate="Time: %{x}<br>Mortality: %{y:.1f}%<extra></extra>",
        ))

        # Annotations for Tier Transitions
        for evt in tier_changes:
            fig.add_vline(
                x=evt.sim_time_str,
                line_width=1.5,
                line_dash="dash",
                line_color="#ec4899",
                annotation_text=f"➔ {evt.new_tier}",
                annotation_position="bottom right",
                annotation_font=dict(size=10, color="#f472b6", family="monospace"),
            )

        # Dark theme layout
        fig.update_layout(
            margin=dict(l=35, r=25, t=15, b=35),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            showlegend=False,
            hovermode="x unified",
            xaxis=dict(
                title=dict(text="Simulation Timeline (HH:MM)", font=dict(size=11, color="#94a3b8", family="monospace")),
                gridcolor="rgba(51, 65, 85, 0.3)",
                tickfont=dict(size=10, color="#94a3b8", family="monospace"),
                showgrid=True,
                zeroline=False,
            ),
            yaxis=dict(
                title=dict(text="Probability (%)", font=dict(size=11, color="#94a3b8", family="monospace")),
                range=[0, 100],
                gridcolor="rgba(51, 65, 85, 0.3)",
                tickfont=dict(size=10, color="#94a3b8", family="monospace"),
                showgrid=True,
                zeroline=False,
            ),
        )

        return fig
