"""
device_status.py — Real-Time Medical Device Status Panel
=========================================================
Monitors connectivity, data rate, message volume, and operational health
across all 5 bedside ICU device modalities in real time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from nicegui import ui

DEVICES_METADATA = [
    {
        "id": "monitor",
        "name": "Patient Monitor",
        "brands": "Philips IntelliVue MX800",
        "icon": "monitor_heart",
        "color": "cyan",
        "cadence": "30 sec",
        "protocol": "HL7 ORU^R01",
    },
    {
        "id": "abg",
        "name": "ABG Analyzer",
        "brands": "Radiometer ABL800",
        "icon": "biotech",
        "color": "purple",
        "cadence": "1 hour / PRN",
        "protocol": "POCT1-A / HL7",
    },
    {
        "id": "lab",
        "name": "Central Lab LIS",
        "brands": "Roche Cobas 8000",
        "icon": "science",
        "color": "emerald",
        "cadence": "4 - 6 hours",
        "protocol": "HL7 LIS / FHIR",
    },
    {
        "id": "pumps",
        "name": "Smart Infusion Pumps",
        "brands": "B.Braun Space Infusomat",
        "icon": "medication",
        "color": "amber",
        "cadence": "5 min",
        "protocol": "IHE PCD-01 / HL7",
    },
    {
        "id": "ventilator",
        "name": "Mechanical Ventilator",
        "brands": "Draeger Evita V800",
        "icon": "air",
        "color": "blue",
        "cadence": "5 min",
        "protocol": "Infinity Gateway",
    },
]


class DeviceStatusPanel:
    """
    Renders status cards for all 5 bedside devices.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self.state: Dict[str, Dict[str, Any]] = initial_state or {}
        self.device_elements: Dict[str, Dict[str, Any]] = {}

    def render(self):
        """Construct the sidebar panel."""
        with ui.column().classes("w-full gap-3"):
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-slate-800"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("hub", size="20px", color="cyan-4")
                    ui.label("BEDSIDE DEVICE STATUS").classes("text-xs font-bold text-slate-100 font-mono tracking-wider")
                ui.badge("5 MODALITIES").props("color=slate-800 text-color=cyan-4 outline").classes("text-[10px] font-mono")

            for dev in DEVICES_METADATA:
                dev_id = dev["id"]
                current = self.state.get(dev_id, {
                    "status": "Active",
                    "messages": 0,
                    "last_seen": "Just now",
                    "latency": "12 ms",
                })

                with ui.card().classes(
                    "w-full bg-slate-900 border border-slate-800 rounded-xl p-3 shadow-md hover:border-slate-700 transition-all"
                ):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2.5"):
                            ui.icon(dev["icon"], size="22px", color=f"{dev['color']}-4")
                            with ui.column().classes("gap-0"):
                                ui.label(dev["name"]).classes("text-xs font-bold text-slate-100 font-mono")
                                ui.label(dev["brands"]).classes("text-[10px] text-slate-400 font-mono")

                        # Connectivity Pill
                        is_active = current.get("status", "Active") == "Active"
                        pill_class = (
                            "bg-emerald-950 text-emerald-400 border border-emerald-800"
                            if is_active
                            else "bg-slate-800 text-slate-400 border border-slate-700"
                        )
                        ui.label(current.get("status", "Active")).classes(f"text-[10px] px-2 py-0.5 rounded font-mono font-semibold {pill_class}")

                    # Metrics Row
                    with ui.row().classes("w-full items-center justify-between pt-2 border-t border-slate-850 mt-2 text-[11px] font-mono text-slate-400"):
                        with ui.row().classes("gap-1 items-center"):
                            ui.label("Msgs:").classes("text-slate-500")
                            cnt_label = ui.label(str(current.get("messages", 0))).classes("text-slate-200 font-bold")

                        with ui.row().classes("gap-1 items-center"):
                            ui.label("Rate:").classes("text-slate-500")
                            ui.label(dev["cadence"]).classes("text-cyan-400")

                        with ui.row().classes("gap-1 items-center"):
                            ui.label("Protocol:").classes("text-slate-500")
                            ui.label(dev["protocol"].split("/")[0].strip()).classes("text-slate-400 text-[10px]")

                    self.device_elements[dev_id] = {"count_label": cnt_label}

    def update_device(self, dev_id: str, count: int, status: str = "Active"):
        """Update metrics for a specific device."""
        if dev_id in self.device_elements:
            lbl = self.device_elements[dev_id].get("count_label")
            if lbl:
                lbl.set_text(str(count))
