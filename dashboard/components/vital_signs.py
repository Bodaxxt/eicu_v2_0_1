"""
ICU Guard v5.0 — Vital Signs Telemetry Panel Component
Renders 6 primary clinical vitals (HR, BP, RR, Temp, SaO2, GCS) with large monospace
readouts, horizontal indicator gauges, color coding (🟢🟡🟠🔴), and 20-point live sparklines.
"""

from typing import Dict, Any, List
from nicegui import ui
from dashboard.utils.constants import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    TIER_STABLE,
    TIER_COLORS,
)


def get_vital_status(vital_key: str, val: float) -> tuple[str, str, float]:
    """
    Returns (color_hex, status_label, progress_ratio [0.0 - 1.0])
    Color coding: 🟢 #32CD32 (Normal), 🟡 #FFD700 (Mild), 🟠 #FF8C00 (Moderate), 🔴 #DC143C (Critical)
    """
    if vital_key == "hr":
        # Normal 60-100
        if 60 <= val <= 100:
            return "#32CD32", "Normal", min(val / 160.0, 1.0)
        elif 101 <= val <= 115 or 50 <= val < 60:
            return "#FFD700", "Mild Stress", min(val / 160.0, 1.0)
        elif 116 <= val <= 130 or 40 <= val < 50:
            return "#FF8C00", "Moderate Tachy", min(val / 160.0, 1.0)
        else:
            return "#DC143C", "Critical Derangement", min(val / 160.0, 1.0)

    elif vital_key == "map":
        # Normal >= 70
        if val >= 70:
            return "#32CD32", "Adequate Perfusion", min(val / 130.0, 1.0)
        elif 65 <= val < 70:
            return "#FFD700", "Borderline Low", min(val / 130.0, 1.0)
        elif 60 <= val < 65:
            return "#FF8C00", "Hypoperfusion Risk", min(val / 130.0, 1.0)
        else:
            return "#DC143C", "Severe Shock", min(val / 130.0, 1.0)

    elif vital_key == "rr":
        # Normal 12-20
        if 12 <= val <= 20:
            return "#32CD32", "Eupnea", min(val / 45.0, 1.0)
        elif 21 <= val <= 25 or 10 <= val < 12:
            return "#FFD700", "Mild Tachypnea", min(val / 45.0, 1.0)
        elif 26 <= val <= 32 or 8 <= val < 10:
            return "#FF8C00", "Respiratory Distress", min(val / 45.0, 1.0)
        else:
            return "#DC143C", "Severe Respiratory Failure", min(val / 45.0, 1.0)

    elif vital_key == "temp":
        # Normal 36.5-37.5
        if 36.5 <= val <= 37.5:
            return "#32CD32", "Normothermia", min((val - 34.0) / 7.0, 1.0)
        elif 37.6 <= val <= 38.2 or 36.0 <= val < 36.5:
            return "#FFD700", "Low-Grade Temp", min((val - 34.0) / 7.0, 1.0)
        elif 38.3 <= val <= 39.0 or 35.0 <= val < 36.0:
            return "#FF8C00", "Fever / Hypothermia", min((val - 34.0) / 7.0, 1.0)
        else:
            return "#DC143C", "High Pyrexia / Hypothermia", min((val - 34.0) / 7.0, 1.0)

    elif vital_key == "sao2":
        # Normal >= 95
        if val >= 95:
            return "#32CD32", "Normal Oxygenation", min(val / 100.0, 1.0)
        elif 92 <= val < 95:
            return "#FFD700", "Mild Desaturation", min(val / 100.0, 1.0)
        elif 88 <= val < 92:
            return "#FF8C00", "Moderate Hypoxemia", min(val / 100.0, 1.0)
        else:
            return "#DC143C", "Critical Hypoxemia", min(val / 100.0, 1.0)

    elif vital_key == "gcs":
        # Normal 15
        if val >= 15:
            return "#32CD32", "Alert / Oriented", 1.0
        elif 13 <= val <= 14:
            return "#FFD700", "Mild Lethargy", val / 15.0
        elif 9 <= val <= 12:
            return "#FF8C00", "Moderate Encephalopathy", val / 15.0
        else:
            return "#DC143C", "Severe Coma (GCS <= 8)", val / 15.0

    return "#32CD32", "Normal", 0.5


def render_sparkline_svg(values: List[float], color: str, width: int = 130, height: int = 32) -> str:
    """Generates an ultra-fast inline SVG sparkline path for 20 points."""
    if not values or len(values) < 2:
        return f'<svg width="{width}" height="{height}"><line x1="0" y1="{height//2}" x2="{width}" y2="{height//2}" stroke="{color}" stroke-width="2" opacity="0.4"/></svg>'

    min_v = min(values)
    max_v = max(values)
    diff = max_v - min_v
    range_v = diff if diff > 0.001 else 1.0

    step = width / max(len(values) - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - min_v) / range_v) * (height - 8) - 4
        pts.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(pts)
    return f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="overflow-hidden">
        <polyline fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="{polyline}" />
        <circle cx="{pts[-1].split(',')[0]}" cy="{pts[-1].split(',')[1]}" r="3" fill="{color}" />
    </svg>
    """


class VitalSignsPanel:
    """Renders and reactively updates the 6 bedside vital signs tiles."""

    VITAL_METRICS = [
        {"key": "hr", "label": "HEART RATE", "unit": "bpm", "icon": "favorite"},
        {"key": "map", "label": "BLOOD PRESSURE (MAP)", "unit": "mmHg", "icon": "speed"},
        {"key": "rr", "label": "RESPIRATORY RATE", "unit": "breaths/min", "icon": "air"},
        {"key": "temp", "label": "CORE TEMPERATURE", "unit": "°C", "icon": "thermostat"},
        {"key": "sao2", "label": "OXYGEN SATURATION", "unit": "%", "icon": "water_drop"},
        {"key": "gcs", "label": "GLASGOW COMA SCALE", "unit": "/15", "icon": "psychology"},
    ]

    def __init__(self):
        self.tiles: Dict[str, Dict[str, Any]] = {}
        self._build_panel()

    def _build_panel(self) -> None:
        """Constructs the 6-grid vital signs layout."""
        with ui.column().classes("w-full gap-3"):
            with ui.row().classes("w-full items-center justify-between pb-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("monitor_heart", size="22px", color="cyan-4")
                    ui.label("CONTINUOUS BEDSIDE TELEMETRY").classes("text-xs font-bold text-slate-300 tracking-wider")
                ui.label("LIVE 1-SEC TELEMETRY STREAM").classes("text-[10px] text-emerald-400 font-mono")

            # 2x3 or 3x2 Grid depending on viewport
            with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"):
                for m in self.VITAL_METRICS:
                    k = m["key"]
                    with ui.card().classes(
                        "glass-card p-3.5 flex flex-col justify-between transition-all duration-300 border border-slate-700/60"
                    ) as card:
                        # Top Row: Label + Icon + Unit
                        with ui.row().classes("w-full justify-between items-center"):
                            with ui.row().classes("items-center gap-1.5"):
                                ui.icon(m["icon"], size="16px", color="slate-400")
                                ui.label(m["label"]).classes("text-[10px] font-bold text-slate-400 tracking-wider")
                            status_badge = ui.label("Normal").classes("text-[10px] font-bold px-2 py-0.5 rounded text-emerald-400 bg-emerald-500/10")

                        # Middle Row: Big Monospace Number + Sparkline
                        with ui.row().classes("w-full items-baseline justify-between mt-2"):
                            with ui.row().classes("items-baseline gap-1.5"):
                                val_label = ui.label("--").classes("text-3xl font-extrabold font-mono text-slate-100 tracking-tight")
                                ui.label(m["unit"]).classes("text-xs text-slate-400 font-medium")

                            sparkline_html = ui.html(render_sparkline_svg([], "#32CD32"))

                        # Bottom Row: Horizontal Gauge Bar
                        bar_container = ui.html("""
                            <div class="w-full bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
                                <div style="width: 50%; height: 100%; background-color: #32CD32; border-radius: 9999px;"></div>
                            </div>
                        """)

                        self.tiles[k] = {
                            "card": card,
                            "val_label": val_label,
                            "status_badge": status_badge,
                            "sparkline_html": sparkline_html,
                            "bar_container": bar_container,
                        }

    def update(self, vitals: Dict[str, float], history: Dict[str, List[float]]) -> None:
        """Refreshes all 6 tiles with new telemetry reading."""
        for m in self.VITAL_METRICS:
            k = m["key"]
            tile = self.tiles.get(k)
            if not tile:
                continue

            raw_val = vitals.get(k, 0.0)
            hist = history.get(k, [])

            # Formatting
            if k == "temp":
                val_text = f"{raw_val:.1f}"
            elif k in {"gcs"}:
                val_text = f"{int(round(raw_val))}"
            elif k == "map":
                sbp = vitals.get("sbp", raw_val * 1.35)
                val_text = f"{int(round(sbp))}/{int(round(raw_val))}"
            else:
                val_text = f"{int(round(raw_val))}"

            # Status and Color
            color, status_text, bar_pct = get_vital_status(k, raw_val)

            # Update Label
            tile["val_label"].text = val_text
            tile["val_label"].style(f"color: {color};")

            # Update Badge
            tile["status_badge"].text = status_text
            tile["status_badge"].style(f"color: {color}; background-color: {color}22; border: 1px solid {color}44;")

            # Update Sparkline SVG
            tile["sparkline_html"].set_content(render_sparkline_svg(hist, color))

            # Update Horizontal Bar
            pct_int = int(bar_pct * 100)
            tile["bar_container"].set_content(f"""
                <div class="w-full bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
                    <div style="width: {pct_int}%; height: 100%; background-color: {color}; border-radius: 9999px; transition: width 0.3s ease;"></div>
                </div>
            """)
