"""
feature_trends.py — Key Physiological & Laboratory Feature Trends Component
=============================================================================
Displays instantaneous values, reference ranges, and acute abnormal flags
for continuous bedside surveillance (HR, MAP, Lactate, Creatinine, Norepinephrine).
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from nicegui import ui


class FeatureTrends:
    """Component rendering physiological parameter status cards."""

    PARAM_CONFIG = [
        {"key": "map", "name": "Mean Arterial Pressure", "abbr": "MAP", "unit": "mmHg", "norm": "70-105", "crit_low": 65.0, "high_crit": False},
        {"key": "hr", "name": "Heart Rate", "abbr": "HR", "unit": "bpm", "norm": "60-100", "crit_high": 120.0, "high_crit": True},
        {"key": "lactate", "name": "Serum Lactate", "abbr": "LAC", "unit": "mmol/L", "norm": "0.5-2.0", "crit_high": 4.0, "high_crit": True},
        {"key": "creatinine", "name": "Serum Creatinine", "abbr": "Cr", "unit": "mg/dL", "norm": "0.6-1.2", "crit_high": 2.0, "high_crit": True},
        {"key": "norepinephrine", "name": "Norepinephrine Rate", "abbr": "NOREPI", "unit": "mcg/kg/min", "norm": "0.0", "crit_high": 0.25, "high_crit": True},
        {"key": "spo2", "name": "Pulse Oximetry", "abbr": "SpO2", "unit": "%", "norm": "95-100", "crit_low": 90.0, "high_crit": False},
    ]

    def __init__(self):
        self.container = None
        self.val_labels: Dict[str, Any] = {}
        self.badge_labels: Dict[str, Any] = {}

    def render(self, initial_features: Optional[Dict[str, Any]] = None) -> None:
        """Constructs the feature trends grid container."""
        feats = initial_features or {}

        with ui.card().classes("glass-card p-4 rounded-xl border border-slate-800 shadow-lg w-full flex flex-col"):
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-slate-800"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("query_stats", size="20px", color="cyan-4")
                    ui.label("KEY PHYSIOLOGICAL & LAB MARKERS").classes("text-xs font-bold text-slate-300 font-mono tracking-wider")

                ui.badge("HL7 Real-Time", color="slate-800").classes("text-xs font-mono text-cyan-400 border border-slate-700")

            with ui.grid(columns=3).classes("w-full gap-3 mt-3"):
                for p in self.PARAM_CONFIG:
                    k = p["key"]
                    val = feats.get(k, 0.0)

                    with ui.card().classes("bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 flex flex-col justify-between"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label(p["abbr"]).classes("text-xs font-bold text-slate-300 font-mono")
                            badge = ui.badge("NORMAL", color="emerald-900").classes("text-[9px] font-mono text-emerald-300")
                            self.badge_labels[k] = badge

                        val_label = ui.label(f"{val:.1f}").classes("text-lg font-extrabold text-slate-100 font-mono my-0.5")
                        self.val_labels[k] = val_label

                        with ui.row().classes("w-full items-center justify-between text-[10px] text-slate-400 font-mono"):
                            ui.label(p["unit"])
                            ui.label(f"Ref: {p['norm']}")

        if initial_features:
            self.update(initial_features)

    def update(self, features: Dict[str, Any]) -> None:
        """Updates feature parameter values and alarm states."""
        for p in self.PARAM_CONFIG:
            k = p["key"]
            if k not in self.val_labels:
                continue

            val = float(features.get(k, 0.0))
            self.val_labels[k].text = f"{val:.2f}" if k in ("lactate", "creatinine", "norepinephrine") else f"{val:.0f}"

            # Check alarms
            is_crit = False
            is_warn = False

            if p.get("high_crit"):
                crit_thresh = p.get("crit_high", 999.0)
                if val >= crit_thresh:
                    is_crit = True
                elif val > (crit_thresh * 0.6) and val > 0:
                    is_warn = True
            else:
                crit_thresh = p.get("crit_low", 0.0)
                if val <= crit_thresh:
                    is_crit = True
                elif val <= (crit_thresh + 5.0):
                    is_warn = True

            badge = self.badge_labels[k]
            if is_crit:
                badge.text = "CRITICAL"
                badge.classes(remove="text-emerald-300 text-amber-300 bg-emerald-900 bg-amber-900", add="text-rose-300 bg-rose-950/80 border border-rose-500")
            elif is_warn:
                badge.text = "ELEVATED" if p.get("high_crit") else "LOW"
                badge.classes(remove="text-emerald-300 text-rose-300 bg-emerald-900 bg-rose-950/80 border-rose-500", add="text-amber-300 bg-amber-900")
            else:
                badge.text = "NORMAL"
                badge.classes(remove="text-rose-300 text-amber-300 bg-rose-950/80 bg-amber-900 border-rose-500", add="text-emerald-300 bg-emerald-900")
