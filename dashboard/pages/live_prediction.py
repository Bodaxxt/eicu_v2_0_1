"""
live_prediction.py — Continuous 5-Minute Live Prediction & Trajectory Dashboard
================================================================================
Renders live continuous ICU risk monitoring: 120 periodic predictions across a
10-hour window, non-downgrading acuity tier transitions, velocity trajectories,
Plotly trend charts, syndrome evolutions, and physiological telemetry trends.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from nicegui import ui, app

from dashboard.components.trajectory_indicator import TrajectoryIndicator
from dashboard.components.trend_chart import TrendChart
from dashboard.components.tier_changes import TierChangesList
from dashboard.components.pattern_evolution import PatternEvolution
from dashboard.components.feature_trends import FeatureTrends
from dashboard.components.prediction_timeline import PredictionTimelineFeed
from dashboard.utils.constants import TIER_COLORS
from dashboard.utils.data_loader import get_data_loader
from severity_agent.hl7.scheduler import PredictionScheduler
from severity_agent.hl7.history import PredictionHistory, PredictionRecord
from severity_agent.hl7.tier_detector import TierChangeDetector, TierChangeEvent
from severity_agent.hl7.trajectory import TrajectoryAnalyzer, TrajectoryResult
from severity_agent.hl7.live_timeline import LiveTimeline


def live_prediction_page(patient_id: Optional[str] = None):
    """Renders the comprehensive Continuous Live Prediction & Trajectory Page."""
    client = ui.context.client
    loader = get_data_loader()

    # Determine Active Patient
    pid = patient_id or app.storage.user.get("active_patient_id") or "224606"
    patient = loader.get_patient(pid)
    if not patient:
        patient = loader.get_random_patient()
        pid = str(patient.get("id", "224606"))
        app.storage.user["active_patient_id"] = pid

    # Continuous Engine Instances
    history_engine = PredictionHistory()
    tier_detector = TierChangeDetector(non_downgrading=True)
    live_timeline = LiveTimeline()
    scheduler = PredictionScheduler(
        history=history_engine,
        tier_detector=tier_detector,
        timeline=live_timeline,
        interval_sim_minutes=5.0,
        speed_multiplier=60.0,
    )

    # UI Components
    trajectory_indicator = TrajectoryIndicator()
    trend_chart = TrendChart()
    tier_changes_list = TierChangesList()
    pattern_evolution = PatternEvolution()
    feature_trends = FeatureTrends()
    timeline_feed = PredictionTimelineFeed()

    # State
    page_state = {
        "current_tier": "STABLE",
        "sim_time_str": "00:00",
        "speed": 60.0,
        "is_running": False,
        "is_paused": False,
        "total_predictions": 0,
    }

    # -------------------------------------------------------------------------
    # 1. Top Header: Demographics, Timer, Controls
    # -------------------------------------------------------------------------
    with ui.header().classes("w-full bg-slate-900 border-b border-slate-800 px-6 py-2.5 items-center justify-between z-20"):
        # Left: Back + Patient Demographics
        with ui.row().classes("items-center gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/live_monitor")).props("flat round color=cyan-4").tooltip(
                "Return to Live Monitor"
            )
            with ui.row().classes("items-center gap-2.5"):
                ui.icon("radar", size="28px", color="cyan-4")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"BED 04 • PATIENT #{pid}").classes("text-sm font-bold text-slate-100 font-mono tracking-wider")
                        tier_badge = ui.badge("STABLE", color="emerald-700").classes("text-xs font-mono font-bold px-2")
                        ui.badge("5-MIN CONTINUOUS", color="slate-800").classes("text-[10px] font-mono text-cyan-300 border border-slate-700")

                    ui.label(
                        f"Age: {patient.get('age', '76')} • Gender: {patient.get('gender', 'M')} • APACHE IV: {patient.get('apache', '48')}"
                    ).classes("text-xs text-slate-400 font-mono")

        # Center: Continuous Simulation Clock
        with ui.row().classes("items-center gap-2 bg-slate-950 px-4 py-1.5 rounded-lg border border-slate-800"):
            ui.html('<div class="pulse-indicator"></div>')
            ui.label("SIM TIME:").classes("text-xs font-bold text-slate-400 font-mono")
            clock_label = ui.label("00:00").classes("text-base font-extrabold text-cyan-400 font-mono")
            ui.label("/ 10:00").classes("text-xs text-slate-500 font-mono")
            pred_count_label = ui.badge("0/120 Preds", color="slate-900").classes("text-[10px] font-mono text-slate-300 border border-slate-700")

        # Right: Speed & Action Controls
        with ui.row().classes("items-center gap-2"):
            ui.label("SPEED:").classes("text-xs font-bold text-slate-400 font-mono mr-1")

            speed_btns = {}
            for spd in [1.0, 5.0, 10.0, 60.0]:
                btn = ui.button(
                    f"{int(spd)}x",
                    on_click=lambda s=spd: set_speed(s),
                ).props(f"{'unelevated color=primary' if spd == 60.0 else 'flat color=slate-4'} dense size=sm").classes(
                    "font-bold font-mono px-2"
                )
                speed_btns[spd] = btn

            ui.separator().props("vertical").classes("mx-1 h-6")

            start_btn = ui.button(
                "Start Sim",
                icon="play_arrow",
                on_click=lambda: start_simulation(),
            ).props("unelevated color=emerald dense size=sm").classes("font-bold")

            pause_btn = ui.button(
                "Pause",
                icon="pause",
                on_click=lambda: toggle_pause(),
            ).props("flat color=amber-4 dense size=sm").classes("font-bold")

            reset_btn = ui.button(
                "Reset",
                icon="restart_alt",
                on_click=lambda: reset_simulation(),
            ).props("flat color=rose-4 dense size=sm").classes("font-bold")

            ui.separator().props("vertical").classes("mx-1 h-6")

            ui.button(
                "HL7 Stream",
                icon="sensors",
                on_click=lambda: ui.navigate.to("/hl7_stream"),
            ).props("size=sm flat color=slate-400").classes("font-mono")

    # -------------------------------------------------------------------------
    # 2. Main Body Container
    # -------------------------------------------------------------------------
    with ui.column().classes("w-full max-w-7xl mx-auto px-6 py-5 gap-5"):

        # Top Section: 3 Large Metric Cards (Mortality, Deterioration, Severe)
        with ui.row().classes("w-full grid grid-cols-1 md:grid-cols-3 gap-4"):
            # Deterioration Card
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-rose-500 rounded-xl shadow-lg"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("DETERIORATION PROBABILITY").classes("text-xs font-bold text-rose-400 font-mono tracking-wider")
                    det_delta_badge = ui.badge("Δ +0.0%", color="slate-900").classes("text-xs font-mono text-rose-300 border border-rose-900")
                with ui.row().classes("items-baseline gap-2 mt-1"):
                    det_val_label = ui.label("15.0%").classes("text-3xl font-extrabold text-rose-400 font-mono")
                    det_total_label = ui.label("from 15.0%").classes("text-xs text-slate-400 font-mono")
                ui.label("High-acuity ICU decompensation risk").classes("text-[11px] text-slate-400 font-mono")

            # Severe Acuity Card
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-cyan-500 rounded-xl shadow-lg"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("SEVERE ACUITY PROBABILITY").classes("text-xs font-bold text-cyan-400 font-mono tracking-wider")
                    sev_delta_badge = ui.badge("Δ +0.0%", color="slate-900").classes("text-xs font-mono text-cyan-300 border border-cyan-900")
                with ui.row().classes("items-baseline gap-2 mt-1"):
                    sev_val_label = ui.label("12.0%").classes("text-3xl font-extrabold text-cyan-400 font-mono")
                    sev_total_label = ui.label("from 12.0%").classes("text-xs text-slate-400 font-mono")
                ui.label("Organ dysfunction escalation likelihood").classes("text-[11px] text-slate-400 font-mono")

            # Mortality Risk Card
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-amber-500 rounded-xl shadow-lg"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("IN-ICU MORTALITY RISK").classes("text-xs font-bold text-amber-400 font-mono tracking-wider")
                    mort_delta_badge = ui.badge("Δ +0.0%", color="slate-900").classes("text-xs font-mono text-amber-300 border border-amber-900")
                with ui.row().classes("items-baseline gap-2 mt-1"):
                    mort_val_label = ui.label("8.0%").classes("text-3xl font-extrabold text-amber-400 font-mono")
                    mort_total_label = ui.label("from 8.0%").classes("text-xs text-slate-400 font-mono")
                ui.label("Physiological mortality prediction").classes("text-[11px] text-slate-400 font-mono")

        # Trajectory Velocity Indicator
        trajectory_indicator.render()

        # Plotly Trend Chart (10-Hour Window)
        trend_chart.render()

        # Bottom 2-Column Split: Clinical Logs & Physiological Telemetry
        with ui.row().classes("w-full grid grid-cols-1 lg:grid-cols-2 gap-5"):
            # Left Column: Tier Transitions & Syndromes
            with ui.column().classes("w-full gap-5"):
                tier_changes_list.render()
                pattern_evolution.render()

            # Right Column: Feature Trends & Live Event Stream
            with ui.column().classes("w-full gap-5"):
                feature_trends.render()
                timeline_feed.render()

    # -------------------------------------------------------------------------
    # Simulation Callback & Update Handlers
    # -------------------------------------------------------------------------
    def handle_prediction_update(record: PredictionRecord):
        """Dispatched on every 5-minute prediction tick."""
        if not getattr(client, "has_socket_connection", True):
            return

        with client:
            page_state["total_predictions"] += 1
            page_state["current_tier"] = record.effective_tier
            page_state["sim_time_str"] = record.sim_time_str

            # Update Header
            clock_label.text = record.sim_time_str
            pred_count_label.text = f"{page_state['total_predictions']}/120 Preds"

            tier_color = TIER_COLORS.get(record.effective_tier, "#32CD32")
            tier_badge.text = record.effective_tier
            tier_badge.style(f"background-color: {tier_color}33; color: {tier_color}; border: 1px solid {tier_color};")

            # Update Metric Cards
            det_pct = record.deterioration_risk * 100.0
            det_val_label.text = f"{det_pct:.1f}%"
            det_sign = "+" if record.delta_deterioration >= 0 else ""
            det_delta_badge.text = f"Δ {det_sign}{record.delta_deterioration*100.0:.1f}%"

            sev_pct = record.severe_risk * 100.0
            sev_val_label.text = f"{sev_pct:.1f}%"
            sev_sign = "+" if record.delta_severe >= 0 else ""
            sev_delta_badge.text = f"Δ {sev_sign}{record.delta_severe*100.0:.1f}%"

            mort_pct = record.mortality_risk * 100.0
            mort_val_label.text = f"{mort_pct:.1f}%"
            mort_sign = "+" if record.delta_mortality >= 0 else ""
            mort_delta_badge.text = f"Δ {mort_sign}{record.delta_mortality*100.0:.1f}%"

            # Update Components
            recent_history = history_engine.get_history(pid)
            traj_res = TrajectoryAnalyzer.analyze(recent_history)
            trajectory_indicator.update(traj_res)

            tier_evts = tier_detector.get_tier_changes(pid)
            trend_chart.update(recent_history, tier_evts)
            tier_changes_list.update(tier_evts)

            pattern_evolution.update(record.active_patterns)
            feature_trends.update(record.features_snapshot)
            timeline_feed.update(live_timeline.get_events(pid))

            if page_state["total_predictions"] >= 120:
                page_state["is_running"] = False
                start_btn.props(remove="disable")
                ui.notify("10-Hour Continuous Prediction Complete (120/120 Preds)!", color="positive")

    scheduler.on_prediction = handle_prediction_update

    def set_speed(speed: float):
        page_state["speed"] = speed
        scheduler.set_speed(speed)
        for s, b in speed_btns.items():
            if s == speed:
                b.props("unelevated color=primary")
            else:
                b.props("flat color=slate-4")

    async def start_simulation():
        if page_state["is_running"]:
            return
        page_state["is_running"] = True
        page_state["is_paused"] = False
        start_btn.props("disable")
        ui.notify("Starting Continuous 10-Hour Live Prediction Engine (60x Speed)...", color="info")
        await scheduler.start(patient_id=pid, total_hours=10.0, speed_multiplier=page_state["speed"])

    def toggle_pause():
        if not page_state["is_running"]:
            return
        if page_state["is_paused"]:
            scheduler.resume()
            page_state["is_paused"] = False
            pause_btn.text = "Pause"
            pause_btn.props("color=amber-4")
        else:
            scheduler.pause()
            page_state["is_paused"] = True
            pause_btn.text = "Resume"
            pause_btn.props("color=emerald-4")

    async def reset_simulation():
        await scheduler.stop()
        history_engine.clear_history(pid)
        tier_detector.reset(pid)
        live_timeline.clear(pid)
        page_state["is_running"] = False
        page_state["is_paused"] = False
        page_state["total_predictions"] = 0
        start_btn.props(remove="disable")
        clock_label.text = "00:00"
        pred_count_label.text = "0/120 Preds"
        tier_badge.text = "STABLE"
        tier_badge.style("background-color: #32CD3233; color: #32CD32; border: 1px solid #32CD32;")
        det_val_label.text = "15.0%"
        sev_val_label.text = "12.0%"
        mort_val_label.text = "8.0%"
        ui.notify("Simulation state reset.", color="secondary")
