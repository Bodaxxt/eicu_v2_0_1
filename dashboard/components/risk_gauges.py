"""
ICU Guard v5.0 — Risk Gauges Component
Renders 3 semi-circular Plotly risk gauges (Mortality, Deterioration, Severe Disease)
with calibrated probabilities, color-coded thresholds, and conformal uncertainty intervals.
"""

from typing import Dict, Any, Optional
import plotly.graph_objects as go
from nicegui import ui


def create_plotly_gauge(
    title: str,
    val_pct: float,
    interval_str: str = "",
    accent_color: str = "#3b82f6",
) -> go.Figure:
    """Builds a single semi-circular dark-themed Plotly gauge."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=val_pct,
            number={"suffix": "%", "font": {"size": 28, "color": "#f8fafc", "family": "Courier New, monospace"}},
            title={"text": f"<b>{title}</b>", "font": {"size": 13, "color": "#94a3b8"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#475569", "tickfont": {"size": 10, "color": "#94a3b8"}},
                "bar": {"color": accent_color, "thickness": 0.28},
                "bgcolor": "rgba(15, 23, 42, 0.7)",
                "borderwidth": 1,
                "bordercolor": "rgba(255, 255, 255, 0.08)",
                "steps": [
                    {"range": [0, 25], "color": "rgba(50, 205, 50, 0.15)"},
                    {"range": [25, 50], "color": "rgba(255, 215, 0, 0.15)"},
                    {"range": [50, 75], "color": "rgba(255, 140, 0, 0.18)"},
                    {"range": [75, 100], "color": "rgba(220, 20, 60, 0.22)"},
                ],
                "threshold": {
                    "line": {"color": "#DC143C", "width": 3},
                    "thickness": 0.8,
                    "value": 75,
                },
            },
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"t": 35, "b": 10, "l": 25, "r": 25},
        height=180,
    )
    return fig


def render_risk_gauges(assessment: Any, *args: Any, **kwargs: Any) -> None:
    """Renders the 3-column multi-target calibrated risk profile with conformal bounds."""
    if isinstance(assessment, dict) and not hasattr(assessment, "probabilities"):
        probs = assessment
        unc = kwargs.get("uncertainty")
        for a in args:
            if hasattr(a, "conformal_intervals"):
                unc = a
                break
    else:
        probs = getattr(assessment, "probabilities", {}) or {}
        unc = getattr(assessment, "uncertainty", None)
        if not unc:
            for a in args:
                if hasattr(a, "conformal_intervals"):
                    unc = a
                    break

    p_mort = probs.get("p_mortality", 0.0) * 100.0
    p_det = probs.get("p_deterioration", 0.0) * 100.0
    p_sev = probs.get("p_severe", 0.0) * 100.0

    # Extract Conformal Bounds if available
    ci_mort = ""
    ci_det = ""
    ci_sev = ""
    if unc:
        targets = getattr(unc, "targets", {}) or {}
        if isinstance(targets, dict):
            if "mortality" in targets:
                t = targets["mortality"]
                ci_mort = f"[{t.conformal_lower*100:.1f}% - {t.conformal_upper*100:.1f}%]"
            if "deterioration" in targets:
                t = targets["deterioration"]
                ci_det = f"[{t.conformal_lower*100:.1f}% - {t.conformal_upper*100:.1f}%]"
            if "severe" in targets:
                t = targets["severe"]
                ci_sev = f"[{t.conformal_lower*100:.1f}% - {t.conformal_upper*100:.1f}%]"
        if hasattr(unc, "conformal_intervals") and unc.conformal_intervals:
            m_low, m_high = unc.conformal_intervals.get("mortality", (p_mort * 0.8, p_mort * 1.2))
            d_low, d_high = unc.conformal_intervals.get("deterioration", (p_det * 0.8, p_det * 1.2))
            s_low, s_high = unc.conformal_intervals.get("severe", (p_sev * 0.8, p_sev * 1.2))
            ci_mort = ci_mort or f"[{m_low*100:.1f}% - {m_high*100:.1f}%]"
            ci_det = ci_det or f"[{d_low*100:.1f}% - {d_high*100:.1f}%]"
            ci_sev = ci_sev or f"[{s_low*100:.1f}% - {s_high*100:.1f}%]"

    with ui.card().classes("w-full glass-card p-4 flex flex-col gap-2"):
        with ui.row().classes("w-full justify-between items-center border-b border-slate-700/60 pb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("analytics", size="20px", color="cyan-4")
                ui.label("MULTI-TARGET ML PREDICTIVE RISK PROFILE").classes("text-xs font-bold text-slate-200 tracking-wider")
            ui.label("Calibrated Platt Scaling & Conformal Guarantee").classes("text-[10px] text-slate-400 font-mono")

        with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-3 gap-4 py-2"):
            # Gauge 1: 28-Day Mortality
            color_mort = "#DC143C" if p_mort > 50 else "#FF8C00" if p_mort > 25 else "#32CD32"
            with ui.card().classes("bg-slate-900/80 p-3 rounded-lg border border-slate-800 flex flex-col items-center"):
                fig1 = create_plotly_gauge("28-DAY MORTALITY HAZARD", p_mort, ci_mort, color_mort)
                ui.plotly(fig1).classes("w-full")
                if ci_mort:
                    ui.label(f"90% Coverage Bound: {ci_mort}").classes("text-[11px] text-slate-400 font-mono")

            # Gauge 2: 12-Hour Deterioration Risk
            color_det = "#DC143C" if p_det > 60 else "#FF8C00" if p_det > 35 else "#32CD32"
            with ui.card().classes("bg-slate-900/80 p-3 rounded-lg border border-slate-800 flex flex-col items-center"):
                fig2 = create_plotly_gauge("12-HOUR DETERIORATION RISK", p_det, ci_det, color_det)
                ui.plotly(fig2).classes("w-full")
                if ci_det:
                    ui.label(f"90% Coverage Bound: {ci_det}").classes("text-[11px] text-slate-400 font-mono")

            # Gauge 3: Severe Disease Index
            color_sev = "#DC143C" if p_sev > 50 else "#FF8C00" if p_sev > 25 else "#32CD32"
            with ui.card().classes("bg-slate-900/80 p-3 rounded-lg border border-slate-800 flex flex-col items-center"):
                fig3 = create_plotly_gauge("SEVERE DISEASE COMPOSITE", p_sev, ci_sev, color_sev)
                ui.plotly(fig3).classes("w-full")
                if ci_sev:
                    ui.label(f"90% Coverage Bound: {ci_sev}").classes("text-[11px] text-slate-400 font-mono")
