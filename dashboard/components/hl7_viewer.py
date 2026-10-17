"""
hl7_viewer.py — Interactive HL7 Message Viewer Component
=========================================================
Renders structured HL7 v2.5 ORU^R01 messages with formatted tabular cards,
abnormal flag color coding (LL/HH red, L/H amber, N green), raw pipe views,
and export/clipboard utilities.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from nicegui import ui

FLAG_STYLES = {
    "HH": "bg-red-950 text-red-400 border border-red-700 font-bold",
    "LL": "bg-red-950 text-red-400 border border-red-700 font-bold",
    "H":  "bg-amber-950 text-amber-300 border border-amber-700",
    "L":  "bg-amber-950 text-amber-300 border border-amber-700",
    "N":  "bg-emerald-950 text-emerald-400 border border-emerald-800",
    "U":  "bg-slate-800 text-slate-400 border border-slate-700",
}

DEVICE_BADGE_COLORS = {
    "monitor": "cyan",
    "abg": "purple",
    "lab": "emerald",
    "pumps": "amber",
    "ventilator": "blue",
}


class HL7MessageCard:
    """
    Renders an individual HL7 message card with toggleable Raw / Formatted views.
    """

    def __init__(self, message_data: Dict[str, Any], raw_hl7_str: Optional[str] = None):
        self.data = message_data
        self.raw_str = raw_hl7_str or self._generate_raw_preview(message_data)
        self.card_container = None
        self.formatted_container = None
        self.raw_container = None
        self.is_raw_visible = False

    def _generate_raw_preview(self, d: Dict[str, Any]) -> str:
        """Fallback raw HL7 string from dict."""
        ts = d.get("timestamp", "").replace("-", "").replace(":", "").replace("T", "")[:14]
        lines = [
            f"MSH|^~\\&|{d.get('device', 'DEVICE')}|{d.get('bed_id', 'BED')}|ICU_GUARD|HOSPITAL|{ts}||ORU^R01|{d.get('message_id', 'MSG001')}|P|2.5",
            f"PID|1||{d.get('patient_id', '000000')}^^^EICU||DOE^PATIENT||19500101|M",
            f"OBR|1|||{d.get('panel', 'TELEMETRY_PANEL')}|||{ts}",
        ]
        for idx, obs in enumerate(d.get("observations", []), start=1):
            loinc = obs.get("loinc", "")
            name = obs.get("name", "")
            val = obs.get("value", "")
            unit = obs.get("unit", "")
            flag = obs.get("flag", "N")
            lines.append(f"OBX|{idx}|NM|{loinc}^{name}^LN||{val}|{unit}||{flag}||F")
        return "\r".join(lines)

    def render(self):
        """Construct the UI component card."""
        dev = self.data.get("device", "DEVICE")
        dev_type = "monitor"
        if "ABL" in dev or "ABG" in dev or "COBAS_B" in dev:
            dev_type = "abg"
        elif "COBAS" in dev or "ARCHITECT" in dev or "ATELLICA" in dev or "LAB" in dev:
            dev_type = "lab"
        elif "SPACE" in dev or "ALARIS" in dev or "AGILIA" in dev or "PUMP" in dev:
            dev_type = "pumps"
        elif "EVITA" in dev or "HAMILTON" in dev or "PURITAN" in dev or "VENT" in dev:
            dev_type = "ventilator"

        badge_color = DEVICE_BADGE_COLORS.get(dev_type, "slate")

        with ui.card().classes(
            "w-full bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all rounded-xl p-4 shadow-lg mb-3"
        ) as self.card_container:
            # Header Row
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-slate-800"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("receipt_long", size="20px", color="cyan-4")
                    ui.label(self.data.get("message_id", "MSG-0000")).classes(
                        "font-mono font-bold text-slate-100 text-sm"
                    )
                    ui.badge(dev).props(f"color={badge_color} outline").classes("text-xs font-mono font-semibold")
                    ui.badge(self.data.get("panel", "PANEL")).props("color=slate-700 text-color=slate-300").classes(
                        "text-xs font-mono"
                    )

                with ui.row().classes("items-center gap-2"):
                    ui.label(f"Bed: {self.data.get('bed_id', 'BED-01')}").classes(
                        "text-xs font-mono text-slate-400 font-bold"
                    )
                    ui.label(f"PID: #{self.data.get('patient_id', '000000')}").classes(
                        "text-xs font-mono text-cyan-400 font-bold bg-slate-950 px-2 py-0.5 rounded border border-slate-800"
                    )
                    ui.label(self.data.get("timestamp", "")[:19]).classes("text-xs text-slate-500 font-mono")

                    # Actions: Toggle Raw & Copy
                    toggle_btn = ui.button(
                        "RAW", on_click=self.toggle_view
                    ).props("size=xs outline color=cyan-4").classes("font-mono")
                    ui.button(
                        icon="content_copy", on_click=lambda: self.copy_to_clipboard()
                    ).props("size=xs flat round color=slate-400").tooltip("Copy Raw HL7")

            # Formatted Observations Grid
            with ui.column().classes("w-full pt-3 gap-2") as self.formatted_container:
                observations = self.data.get("observations", [])
                if observations:
                    with ui.grid(columns="repeat(auto-fill, minmax(220px, 1fr))").classes("w-full gap-2.5"):
                        for obs in observations:
                            flag = obs.get("flag", "N")
                            flag_style = FLAG_STYLES.get(flag, FLAG_STYLES["N"])

                            with ui.row().classes(
                                "items-center justify-between bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-850"
                            ):
                                with ui.column().classes("gap-0"):
                                    ui.label(obs.get("name", "OBS")).classes(
                                        "text-xs font-semibold text-slate-200 font-mono"
                                    )
                                    ui.label(obs.get("loinc", "")).classes("text-[10px] text-slate-500 font-mono")
                                with ui.row().classes("items-center gap-1.5"):
                                    ui.label(f"{obs.get('value', 0):.4g}").classes(
                                        "text-sm font-extrabold text-slate-100 font-mono"
                                    )
                                    ui.label(obs.get("unit", "")).classes("text-[10px] text-slate-400 font-mono")
                                    ui.label(flag).classes(f"text-[10px] px-1.5 py-0.5 rounded {flag_style}")
                else:
                    ui.label("No OBX observation segments recorded.").classes("text-xs text-slate-500 italic")

            # Raw Monospaced Pre-formatted Box (Initially hidden)
            with ui.column().classes("w-full pt-3 hidden") as self.raw_container:
                raw_formatted = self.raw_str.replace("\r", "\n")
                ui.code(raw_formatted, language="hl7").classes(
                    "w-full text-xs font-mono bg-slate-950 text-cyan-300 p-3 rounded-lg border border-slate-800 overflow-x-auto whitespace-pre"
                )

    def toggle_view(self):
        """Toggle between formatted card view and raw HL7 pipe text."""
        self.is_raw_visible = not self.is_raw_visible
        if self.is_raw_visible:
            self.formatted_container.classes(add="hidden")
            self.raw_container.classes(remove="hidden")
        else:
            self.formatted_container.classes(remove="hidden")
            self.raw_container.classes(add="hidden")

    def copy_to_clipboard(self):
        """Copy raw HL7 string to user clipboard."""
        escaped = self.raw_str.replace("\r", "\\n").replace("'", "\\'")
        ui.run_javascript(f"navigator.clipboard.writeText('{escaped}')")
        ui.notify("Copied HL7 message to clipboard!", type="positive", timeout=1500)
