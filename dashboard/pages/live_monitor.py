"""
ICU Guard v5.0 — Real-Time Live Monitor Dashboard Page
Integrates continuous telemetry streaming, vital sign gauges, 20-point sparklines,
AI syndrome detection, live timeline feed, and speed/pause controls.
"""

import asyncio
from typing import Dict, Any, Optional
from nicegui import ui, app

from dashboard.config import config
from dashboard.utils.constants import TIER_COLORS
from dashboard.utils.data_loader import get_data_loader
from dashboard.streaming.data_streamer import DataStreamer, StreamFrame
from dashboard.streaming.live_analyzer import LiveAnalyzer, LiveAnalysisResult
from dashboard.components.vital_signs import VitalSignsPanel
from dashboard.components.ai_analysis import AIAnalysisPanel
from dashboard.components.timeline import TimelineFeed
from dashboard.components.alert_system import AlertSystem


def live_monitor_page(patient_id: Optional[str] = None):
    """Renders the comprehensive Phase 2 ICU Live Monitor."""
    client = ui.context.client
    loader = get_data_loader()

    # Determine Active Patient
    pid = patient_id or app.storage.user.get("active_patient_id")
    patient = loader.get_patient(pid) if pid else None
    if not patient:
        patient = loader.get_random_patient()
        app.storage.user["active_patient_id"] = patient.get("id")

    # State Holders
    streamer_holder: Dict[str, Any] = {"streamer": None, "task": None, "elapsed_seconds": 0}
    analyzer = LiveAnalyzer(history_len=20)
    alert_system = AlertSystem(enable_sound=True)

    tier_color = TIER_COLORS.get(patient.get("tier", "STABLE"), "#32CD32")

    # -------------------------------------------------------------------------
    # 1. Top Header: Demographics, Timer & Speed Controls
    # -------------------------------------------------------------------------
    with ui.header().classes("w-full bg-slate-900 border-b border-slate-800 px-6 py-2.5 items-center justify-between z-20"):
        # Left: Back + Patient Demographics
        with ui.row().classes("items-center gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round color=cyan-4").tooltip(
                "Return to Patient Selection Registry"
            )
            with ui.row().classes("items-center gap-2"):
                ui.icon("local_hospital", size="28px", color="cyan-4")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(f"BED 04 • PATIENT #{patient.get('id')}").classes("text-base font-bold text-slate-100 font-mono")
                        ui.badge(patient.get("tier", "STABLE")).style(
                            f"border: 1px solid {tier_color}; color: {tier_color}; background-color: {tier_color}22; font-weight: bold; font-size: 0.7rem; padding: 2px 6px;"
                        )
                    ui.label(
                        f"Age: {patient.get('age', 'N/A')} • Gender: {patient.get('gender', 'N/A')} • APACHE IV: {patient.get('apache', 'N/A')}"
                    ).classes("text-xs text-slate-400 font-mono")

        # Center: Telemetry Timer
        with ui.row().classes("items-center gap-2 bg-slate-950 px-4 py-1.5 rounded-lg border border-slate-800"):
            ui.html('<div class="pulse-indicator"></div>')
            ui.label("REC TIME:").classes("text-xs font-bold text-slate-400 font-mono")
            timer_label = ui.label("00:00").classes("text-sm font-extrabold text-cyan-400 font-mono")

        # Right: Speed Controls + Play/Pause/Stop
        with ui.row().classes("items-center gap-2"):
            ui.label("SPEED:").classes("text-xs font-bold text-slate-400 font-mono mr-1")

            speed_buttons: Dict[float, Any] = {}
            for spd in [1.0, 5.0, 10.0, 50.0]:
                btn = ui.button(
                    f"{int(spd)}x",
                    on_click=lambda s=spd: set_streaming_speed(s),
                ).props(f"{'unelevated color=primary' if spd == 1.0 else 'flat color=slate-4'} dense size=sm").classes(
                    "font-bold font-mono px-2"
                )
                speed_buttons[spd] = btn

            ui.separator().props("vertical").classes("mx-1 h-6")

            pause_btn = ui.button(
                "Pause",
                icon="pause",
                on_click=lambda: toggle_pause(),
            ).props("flat color=amber-4 dense size=sm").classes("font-bold")

            stop_btn = ui.button(
                "Stop",
                icon="stop",
                on_click=lambda: stop_stream(),
            ).props("flat color=rose-4 dense size=sm").classes("font-bold")

            ui.separator().props("vertical").classes("mx-1 h-6")

            ui.button(
                "Live Prediction",
                icon="radar",
                on_click=lambda: ui.navigate.to(
                    f"/live_prediction?patient_id={patient.get('id')}"
                ),
            ).props("unelevated color=indigo-7 dense size=sm").classes("font-bold")

            ui.button(
                "HL7 Stream",
                icon="sensors",
                on_click=lambda: ui.navigate.to("/hl7_stream"),
            ).props("unelevated color=cyan-7 dense size=sm").classes("font-bold")

            ui.button(
                "Final Assessment",
                icon="summarize",
                on_click=lambda: ui.navigate.to(
                    f"/final_assessment?patient_id={patient.get('id')}"
                ),
            ).props("unelevated color=indigo dense size=sm").classes("font-bold")

    # -------------------------------------------------------------------------
    # 2. Main Telemetry Dashboard Body
    # -------------------------------------------------------------------------
    with ui.column().classes("w-full max-w-7xl mx-auto px-6 py-5 gap-5"):

        # Upper Section: 2 Columns (Left: 6 Vitals + Sparklines, Right: AI Analysis Panel)
        with ui.row().classes("w-full grid grid-cols-1 lg:grid-cols-12 gap-5"):
            # Left: Vitals Panel (7 cols on lg)
            with ui.column().classes("lg:col-span-7 w-full"):
                vitals_panel = VitalSignsPanel()

            # Right: AI Analysis Panel (5 cols on lg)
            with ui.column().classes("lg:col-span-5 w-full"):
                ai_panel = AIAnalysisPanel()

        # Lower Section: Chronological Timeline Feed
        timeline_feed = TimelineFeed(max_entries=200)

        # Bottom Progress Bar
        with ui.column().classes("w-full gap-1 pt-2"):
            with ui.row().classes("w-full justify-between items-center text-[10px] text-slate-400 font-mono"):
                ui.label("ICU TELEMETRY BUFFER PROGRESS")
                progress_label = ui.label("0%")
            progress_bar = ui.linear_progress(value=0.0, show_value=False).props("color=cyan-5 rounded stripe animate").classes(
                "h-2 bg-slate-800"
            )

    # -------------------------------------------------------------------------
    # 3. Final Clinical Summary Modal Dialog
    # -------------------------------------------------------------------------
    summary_dialog = ui.dialog().classes("z-50")

    def show_final_summary(last_analysis: Optional[LiveAnalysisResult]) -> None:
        summary_dialog.clear()
        with summary_dialog, ui.card().classes("w-[620px] max-w-[95vw] glass-card-elevated p-6 gap-4 border border-slate-700"):
            with ui.row().classes("w-full justify-between items-center border-b border-slate-700 pb-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("assignment_turned_in", size="28px", color="cyan-4")
                    ui.label("TELEMETRY SESSION CONCLUDED").classes("text-lg font-bold text-white")

                if last_analysis:
                    c = last_analysis.tier_color
                    ui.badge(last_analysis.current_tier).style(
                        f"border: 1px solid {c}; color: {c}; background-color: {c}22; font-weight: bold; padding: 4px 10px;"
                    )

            ui.label(
                f"Completed surveillance stream for Patient #{patient.get('id')}. Telemetry buffer processed completely."
            ).classes("text-xs text-slate-300 leading-relaxed")

            if last_analysis:
                with ui.row().classes("w-full grid grid-cols-2 gap-3 py-1"):
                    with ui.card().classes("bg-slate-900/80 p-3 rounded border border-slate-800"):
                        ui.label("FINAL TRIAGE TIER").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(last_analysis.current_tier).classes("text-sm font-bold text-slate-100")

                    with ui.card().classes("bg-slate-900/80 p-3 rounded border border-slate-800"):
                        ui.label("TRAJECTORY PATH").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(last_analysis.trajectory.replace("_", " ")).classes("text-sm font-bold text-slate-100")

                with ui.card().classes("w-full bg-slate-900/90 p-3 rounded border border-slate-700 mt-1"):
                    ui.label("DISCHARGE / ESCALATION PROTOCOL:").classes("text-[10px] font-bold text-amber-400")
                    ui.label(last_analysis.recommended_action).classes("text-xs text-slate-300 mt-1 leading-relaxed")

            with ui.row().classes("w-full justify-end items-center gap-3 pt-3 border-t border-slate-700"):
                ui.button("Restart Stream", icon="replay", on_click=lambda: (summary_dialog.close(), restart_stream())).props(
                    "outlined color=cyan-3"
                )
                ui.button(
                    "Return to Registry",
                    icon="arrow_back",
                    on_click=lambda: (summary_dialog.close(), ui.navigate.to("/")),
                ).props("unelevated color=primary").classes("font-bold")

        summary_dialog.open()

    # -------------------------------------------------------------------------
    # 4. Telemetry Tick & Synchronization Handlers
    # -------------------------------------------------------------------------
    last_analysis_holder: Dict[str, Any] = {"result": None}

    def on_frame_received(frame: StreamFrame) -> None:
        """Called synchronously/asynchronously on every incoming telemetry tick."""
        if not getattr(client, "has_socket_connection", True):
            streamer = streamer_holder.get("streamer")
            if streamer:
                streamer.stop()
            return

        with client:
            try:
                # 1. Run inference in LiveAnalyzer
                analysis = analyzer.analyze_frame(frame)
                last_analysis_holder["result"] = analysis

                # 2. Update Vital Signs Tiles & Sparklines
                vitals_panel.update(frame.vitals, analysis.vitals_history)

                # 3. Update AI Clinical Analysis Card
                ai_panel.update(analysis)

                # 4. Append to Live Timeline Feed
                timeline_feed.add_entry(frame, analysis)

                # 5. Trigger Real-Time Alarms
                for alert in analysis.new_alerts:
                    alert_system.trigger_alert(alert)

                # 6. Update Elapsed Timer & Progress Bar
                mins = frame.tick // 60
                secs = frame.tick % 60
                timer_label.text = f"{mins:02d}:{secs:02d}"

                progress_ratio = frame.progress_pct / 100.0
                progress_bar.value = progress_ratio
                progress_label.text = f"{int(frame.progress_pct)}%"

                if frame.is_terminal:
                    show_final_summary(analysis)
            except Exception as exc:
                import logging
                logging.getLogger("icu_guard.live_monitor").error("Error in on_frame_received: %s", exc, exc_info=True)

    def on_stream_completed() -> None:
        if not getattr(client, "has_socket_connection", True):
            return
        with client:
            show_final_summary(last_analysis_holder["result"])

    # -------------------------------------------------------------------------
    # 5. Streaming Control Actions
    # -------------------------------------------------------------------------
    def set_streaming_speed(speed: float) -> None:
        streamer = streamer_holder.get("streamer")
        if streamer:
            streamer.set_speed(speed)
        for s, btn in speed_buttons.items():
            if s == speed:
                btn.props("unelevated color=primary")
            else:
                btn.props("flat color=slate-4")
        ui.notify(f"Telemetry speed set to {int(speed)}x", type="info", position="bottom-right")

    def toggle_pause() -> None:
        streamer: DataStreamer = streamer_holder.get("streamer")
        if not streamer:
            return

        if streamer.is_paused:
            streamer.resume()
            pause_btn.text = "Pause"
            pause_btn.props("icon=pause color=amber-4")
            ui.notify("Telemetry Stream Resumed", type="positive", position="bottom-right")
        else:
            streamer.pause()
            pause_btn.text = "Resume"
            pause_btn.props("icon=play_arrow color=emerald-4")
            ui.notify("Telemetry Stream Paused", type="warning", position="bottom-right")

    def stop_stream() -> None:
        streamer: DataStreamer = streamer_holder.get("streamer")
        if streamer:
            streamer.stop()
        if getattr(client, "has_socket_connection", True):
            with client:
                show_final_summary(last_analysis_holder["result"])

    def restart_stream() -> None:
        streamer: DataStreamer = streamer_holder.get("streamer")
        if streamer:
            streamer.stop()
        start_streaming_lifecycle()

    def start_streaming_lifecycle() -> None:
        streamer = DataStreamer(
            patient_record=patient,
            total_ticks=60,
            speed=1.0,
            on_tick=on_frame_received,
            on_complete=on_stream_completed,
        )
        streamer_holder["streamer"] = streamer
        streamer_holder["task"] = asyncio.create_task(streamer.run_loop())

    # Automatically bootstrap live telemetry on mount and clean up on disconnect
    ui.timer(0.1, lambda: start_streaming_lifecycle(), once=True)
    client.on_disconnect(lambda: stop_stream())
