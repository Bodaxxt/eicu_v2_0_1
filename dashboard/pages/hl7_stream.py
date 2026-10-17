"""
hl7_stream.py — Real-Time HL7 Telemetry Stream & Device Status Page
===================================================================
Displays live continuous HL7 v2.5 streams from Bedside Monitors, ABG Analyzers,
Central Lab LIS, Smart Infusion Pumps, and Mechanical Ventilators.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from nicegui import ui, app

from dashboard.components.hl7_viewer import HL7MessageCard
from dashboard.components.device_status import DeviceStatusPanel
from dashboard.components.hl7_stats import HL7StatsBar
from hl7_simulator.core.message_builder import HL7MessageBuilder, LOINC
from severity_agent.hl7.parser import HL7Parser


def hl7_stream_page():
    """Renders the comprehensive HL7 Stream & Medical Device Integration Page."""
    client = ui.context.client

    # Local in-memory stream buffer for this session
    stream_state = {
        "messages": [],
        "filter_device": "ALL",
        "filter_flag": "ALL",
        "search_query": "",
        "total_count": 0,
        "critical_count": 0,
        "start_time": datetime.now(),
    }

    # Pre-populate sample realistic stream messages from the 5 devices
    sample_msgs = [
        HL7MessageBuilder.monitor_message("224606", "ICU_BED_04", 124.0, 76.0, 38.0, 48.0, 30.0, 84.0, 39.1).to_string(),
        HL7MessageBuilder.abg_message("224606", "ICU_BED_04", 7.15, 65.0, 31.0, 8.4).to_string(),
        (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="BBRAUN_SPACE", panel_id="INFUSION_PARAMS")
            .add_observation(LOINC.NORADRENALINE_RATE, 0.45)
            .add_observation(LOINC.EPINEPHRINE_RATE, 0.25)
            .add_observation(LOINC.PROPOFOL_RATE, 70.0)
            .build()
            .to_string()
        ),
        (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="DRAEGER_EVITA", panel_id="VENTILATOR_PARAMS")
            .add_observation(LOINC.FIO2, 80.0)
            .add_observation(LOINC.PEEP, 14.0)
            .add_observation(LOINC.TIDAL_VOLUME, 400.0)
            .add_observation(LOINC.PEAK_PRESSURE, 32.0)
            .build()
            .to_string()
        ),
        (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="ROCHE_COBAS_8000", panel_id="CHEM_PANEL")
            .add_observation(LOINC.CREATININE, 2.75)
            .add_observation(LOINC.BUN, 52.0)
            .add_observation(LOINC.WBC, 19.5)
            .add_observation(LOINC.PLATELETS, 88.0)
            .add_observation(LOINC.POTASSIUM, 5.2)
            .build()
            .to_string()
        ),
    ]

    for raw in sample_msgs:
        p = HL7Parser.parse(raw)
        if p:
            stream_state["messages"].append({"parsed": p.to_dict(), "raw": raw})
            stream_state["total_count"] += 1
            for obs in p.observations:
                if obs.flag in ("HH", "LL"):
                    stream_state["critical_count"] += 1

    stats_bar = HL7StatsBar()
    device_panel = DeviceStatusPanel()

    # -------------------------------------------------------------------------
    # 1. Top Header: Demographics, Status, Navigation
    # -------------------------------------------------------------------------
    with ui.header().classes("w-full bg-slate-900 border-b border-slate-800 px-6 py-2.5 items-center justify-between z-20"):
        with ui.row().classes("items-center gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/live_monitor")).props("flat round color=cyan-4").tooltip(
                "Return to Live Monitor"
            )
            with ui.row().classes("items-center gap-2.5"):
                ui.icon("sensors", size="26px", color="cyan-4")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label("HL7 TELEMETRY STREAM & INGESTION GATEWAY").classes("text-sm font-extrabold text-slate-100 font-mono tracking-wider")
                        ui.badge("PORT 6661 MLLP").props("color=emerald outline").classes("text-[10px] font-mono")
                    ui.label("Multi-Device Egyptian Bedside Interoperability Layer (HL7 v2.5 ORU^R01)").classes("text-xs text-slate-400 font-mono")

        # Center / Right Actions
        with ui.row().classes("items-center gap-3"):
            ui.button(
                "Live Monitor",
                icon="monitor_heart",
                on_click=lambda: ui.navigate.to("/live_monitor"),
            ).props("size=sm outline color=cyan-4").classes("font-mono font-bold")
            ui.button(
                "Patient Registry",
                icon="people",
                on_click=lambda: ui.navigate.to("/"),
            ).props("size=sm flat color=slate-400").classes("font-mono")

    # -------------------------------------------------------------------------
    # 2. Main Page Layout
    # -------------------------------------------------------------------------
    with ui.column().classes("w-full min-h-screen bg-slate-950 p-6 gap-5"):
        # Top KPI Stats Banner
        stats_bar.render()
        stats_bar.update(
            total=stream_state["total_count"],
            throughput=2.5,
            alerts=stream_state["critical_count"],
            latency_ms=7.8,
        )

        # Toolbar: Search, Filters & Export
        with ui.card().classes("w-full bg-slate-900 border border-slate-800 p-3.5 rounded-xl shadow-md"):
            with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                # Left: Modality Filter Buttons
                with ui.row().classes("items-center gap-1.5"):
                    ui.label("DEVICE:").classes("text-xs font-bold text-slate-400 font-mono mr-1")
                    modalities = ["ALL", "MONITOR", "ABG", "LAB", "PUMPS", "VENTILATOR"]
                    filter_btns = {}

                    def set_modality(m_val):
                        stream_state["filter_device"] = m_val
                        refresh_feed()

                    for m in modalities:
                        btn = ui.button(m, on_click=lambda val=m: set_modality(val)).props("size=xs outline color=cyan-4").classes("font-mono text-[11px]")
                        filter_btns[m] = btn

                # Middle: Severity Filter
                with ui.row().classes("items-center gap-1.5"):
                    ui.label("FLAG:").classes("text-xs font-bold text-slate-400 font-mono mr-1")
                    flags = ["ALL", "CRITICAL (HH/LL)", "ABNORMAL (H/L)", "NORMAL (N)"]
                    def set_flag(f_val):
                        stream_state["filter_flag"] = f_val
                        refresh_feed()
                    for f in flags:
                        ui.button(f.split()[0], on_click=lambda val=f: set_flag(val)).props("size=xs flat color=slate-300").classes("font-mono text-[11px]")

                # Right: Export & Test Packet Trigger
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Trigger Test Packet",
                        icon="send",
                        on_click=lambda: inject_test_packet(),
                    ).props("size=sm color=cyan-6 text-color=slate-950").classes("font-mono font-bold")

                    # Export Dropdown Menu
                    with ui.button("Export", icon="download").props("size=sm outline color=slate-300").classes("font-mono"):
                        with ui.menu().classes("bg-slate-900 border border-slate-800 text-slate-200"):
                            ui.menu_item("Export as JSON", on_click=lambda: export_data("json"))
                            ui.menu_item("Export as CSV", on_click=lambda: export_data("csv"))
                            ui.menu_item("Export Raw HL7", on_click=lambda: export_data("hl7"))

        # Two-Column Workspace: Live Stream (70%) + Device Status Sidebar (30%)
        with ui.row().classes("w-full gap-5 items-start"):
            # Left: Feed Container
            with ui.column().classes("flex-1 min-w-[600px] gap-3") as feed_column:
                with ui.row().classes("w-full items-center justify-between pb-1"):
                    with ui.row().classes("items-center gap-2"):
                        ui.html('<div class="pulse-indicator"></div>')
                        ui.label("LIVE TELEMETRY INGESTION FEED").classes("text-xs font-bold text-slate-200 font-mono tracking-wider")
                    feed_counter = ui.label(f"{len(stream_state['messages'])} PACKETS LOADED").classes("text-xs font-mono text-cyan-400 font-semibold")

                feed_cards_container = ui.column().classes("w-full gap-3")

            # Right: Sidebar (Device Status)
            with ui.column().classes("w-[340px] shrink-0 gap-4"):
                device_panel.render()

    def refresh_feed():
        """Render filtered message cards into feed_cards_container."""
        feed_cards_container.clear()
        dev_filter = stream_state["filter_device"]
        flag_filter = stream_state["filter_flag"]

        matched_count = 0
        with feed_cards_container:
            for item in reversed(stream_state["messages"]):
                p = item["parsed"]
                raw = item["raw"]
                dev = p.get("device", "").upper()

                # Filter by device
                if dev_filter != "ALL":
                    if dev_filter == "MONITOR" and not ("INTELLIVUE" in dev or "CARESCAPE" in dev or "BENEVISION" in dev):
                        continue
                    elif dev_filter == "ABG" and not ("ABL" in dev or "ABG" in dev or "COBAS_B" in dev or "GEM" in dev):
                        continue
                    elif dev_filter == "LAB" and not ("COBAS_8000" in dev or "ARCHITECT" in dev or "ATELLICA" in dev):
                        continue
                    elif dev_filter == "PUMPS" and not ("SPACE" in dev or "ALARIS" in dev or "AGILIA" in dev):
                        continue
                    elif dev_filter == "VENTILATOR" and not ("EVITA" in dev or "HAMILTON" in dev or "PURITAN" in dev):
                        continue

                # Filter by flag
                if flag_filter != "ALL":
                    flags_in_msg = {obs.get("flag") for obs in p.get("observations", [])}
                    if "CRITICAL" in flag_filter and not (flags_in_msg & {"HH", "LL"}):
                        continue
                    elif "ABNORMAL" in flag_filter and not (flags_in_msg & {"H", "L", "HH", "LL"}):
                        continue
                    elif "NORMAL" in flag_filter and ("HH" in flags_in_msg or "LL" in flags_in_msg or "H" in flags_in_msg or "L" in flags_in_msg):
                        continue

                card = HL7MessageCard(message_data=p, raw_hl7_str=raw)
                card.render()
                matched_count += 1

        feed_counter.set_text(f"{matched_count} / {len(stream_state['messages'])} PACKETS DISPLAYED")

    def inject_test_packet():
        """Inject a simulated live packet into feed."""
        import random
        hr = random.uniform(90.0, 130.0)
        map_bp = random.uniform(45.0, 75.0)
        msg_str = HL7MessageBuilder.monitor_message("224606", "ICU_BED_04", hr, 88.0, 48.0, map_bp, 26.0, 88.0, 38.6).to_string()
        p = HL7Parser.parse(msg_str)
        if p:
            stream_state["messages"].append({"parsed": p.to_dict(), "raw": msg_str})
            stream_state["total_count"] += 1
            if map_bp < 55.0 or hr > 120.0:
                stream_state["critical_count"] += 1

            stats_bar.update(
                total=stream_state["total_count"],
                throughput=3.2,
                alerts=stream_state["critical_count"],
                latency_ms=7.2,
            )
            refresh_feed()
            ui.notify("Injected live HL7 packet from Philips IntelliVue!", type="positive", timeout=1200)

    def export_data(fmt: str):
        """Export buffered stream data."""
        if fmt == "json":
            content = json.dumps([m["parsed"] for m in stream_state["messages"]], indent=2)
            ui.download(content.encode("utf-8"), filename="hl7_stream_export.json")
        elif fmt == "csv":
            rows = ["timestamp,device,bed_id,patient_id,loinc,name,value,unit,flag"]
            for m in stream_state["messages"]:
                p = m["parsed"]
                for obs in p.get("observations", []):
                    rows.append(f"{p.get('timestamp')},{p.get('device')},{p.get('bed_id')},{p.get('patient_id')},{obs.get('loinc')},{obs.get('name')},{obs.get('value')},{obs.get('unit')},{obs.get('flag')}")
            ui.download("\n".join(rows).encode("utf-8"), filename="hl7_observations.csv")
        elif fmt == "hl7":
            raw_text = "\n\n".join([m["raw"] for m in stream_state["messages"]])
            ui.download(raw_text.encode("utf-8"), filename="raw_hl7_stream.hl7")

    # Initial feed render
    refresh_feed()
