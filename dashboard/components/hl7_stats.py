"""
hl7_stats.py — Telemetry Ingestion Metrics & KPI Cards
======================================================
Displays live statistics: throughput, total messages, active devices,
critical alert count, latency, and operational uptime.
"""

from __future__ import annotations

from typing import Any, Dict
from nicegui import ui


class HL7StatsBar:
    """
    Renders top KPI banner cards for the HL7 streaming dashboard.
    """

    def __init__(self):
        self.total_msgs_label = None
        self.throughput_label = None
        self.active_dev_label = None
        self.alerts_label = None
        self.latency_label = None
        self.uptime_label = None

    def render(self):
        """Construct the 5-card metric banner."""
        with ui.grid(columns="repeat(auto-fit, minmax(180px, 1fr))").classes("w-full gap-3"):
            # 1. Total Messages
            with ui.card().classes("bg-slate-900 border border-slate-800 p-3.5 rounded-xl"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("TOTAL PACKETS").classes("text-[11px] font-bold text-slate-400 font-mono tracking-wider")
                    ui.icon("inventory_2", size="18px", color="cyan-4")
                self.total_msgs_label = ui.label("0").classes("text-2xl font-extrabold text-slate-100 font-mono mt-1")
                ui.label("HL7 v2.5 ORU^R01").classes("text-[10px] text-slate-500 font-mono")

            # 2. Ingestion Throughput
            with ui.card().classes("bg-slate-900 border border-slate-800 p-3.5 rounded-xl"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("THROUGHPUT").classes("text-[11px] font-bold text-slate-400 font-mono tracking-wider")
                    ui.icon("speed", size="18px", color="emerald-4")
                self.throughput_label = ui.label("0.0 msg/s").classes("text-2xl font-extrabold text-emerald-400 font-mono mt-1")
                ui.label("MLLP Port 6661").classes("text-[10px] text-slate-500 font-mono")

            # 3. Active Devices
            with ui.card().classes("bg-slate-900 border border-slate-800 p-3.5 rounded-xl"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("ACTIVE DEVICES").classes("text-[11px] font-bold text-slate-400 font-mono tracking-wider")
                    ui.icon("sensors", size="18px", color="blue-4")
                self.active_dev_label = ui.label("5 / 5").classes("text-2xl font-extrabold text-blue-400 font-mono mt-1")
                ui.label("All Modalities Online").classes("text-[10px] text-slate-500 font-mono")

            # 4. Critical Abnormal Flags (HH / LL)
            with ui.card().classes("bg-slate-900 border border-slate-800 p-3.5 rounded-xl"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("CRITICAL VALUES").classes("text-[11px] font-bold text-slate-400 font-mono tracking-wider")
                    ui.icon("warning", size="18px", color="red-4")
                self.alerts_label = ui.label("0").classes("text-2xl font-extrabold text-red-400 font-mono mt-1")
                ui.label("Panic Alerts (HH / LL)").classes("text-[10px] text-slate-500 font-mono")

            # 5. Pipeline Latency
            with ui.card().classes("bg-slate-900 border border-slate-800 p-3.5 rounded-xl"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("AVG LATENCY").classes("text-[11px] font-bold text-slate-400 font-mono tracking-wider")
                    ui.icon("bolt", size="18px", color="amber-4")
                self.latency_label = ui.label("8.4 ms").classes("text-2xl font-extrabold text-amber-300 font-mono mt-1")
                ui.label("Ingest to Assessment").classes("text-[10px] text-slate-500 font-mono")

    def update(self, total: int, throughput: float, alerts: int, latency_ms: float = 8.5):
        """Update live values."""
        if self.total_msgs_label:
            self.total_msgs_label.set_text(f"{total:,}")
        if self.throughput_label:
            self.throughput_label.set_text(f"{throughput:.1f} msg/s")
        if self.alerts_label:
            self.alerts_label.set_text(str(alerts))
        if self.latency_label:
            self.latency_label.set_text(f"{latency_ms:.1f} ms")
