"""
ventilator_scenarios.py — Mechanical Ventilator Clinical Scenarios
===================================================================
Defines mechanical ventilation settings & lung mechanics:
1. No Ventilation (Extubated / Spontaneous breathing on room air)
2. Moderate Ventilation (Standard post-operative or recovering lung)
3. Severe ARDS (High FiO2, high PEEP, lung-protective ventilation strategy)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any

logger = logging.getLogger("hl7_simulator.vent_scenarios")


@dataclass
class VentTarget:
    """Target endpoints for a ventilator setting or monitored parameter."""
    start: float
    end: float
    noise_std_percent: float = 0.005


class VentilatorTrajectory:
    """Computes interpolated ventilator parameters across clinical time."""

    def __init__(self, name: str, mode: str, verdict: str, targets: Dict[str, VentTarget]):
        self.name = name
        self.mode = mode
        self.verdict = verdict
        self.targets = targets

    def sample(self, progress: float = 0.0, add_noise: bool = True) -> Dict[str, Any]:
        p = max(0.0, min(1.0, progress))
        readings: Dict[str, Any] = {"mode": self.mode}

        for param, target in self.targets.items():
            base_val = target.start + (target.end - target.start) * p
            if add_noise and target.noise_std_percent > 0 and base_val > 0:
                import random
                noise = random.gauss(0, base_val * target.noise_std_percent)
                val = max(0.0, base_val + noise)
            else:
                val = base_val

            if param in ("peep", "peak_pressure"):
                readings[param] = round(val, 1)
            elif param in ("fio2", "tidal_volume", "respiratory_rate"):
                readings[param] = round(val, 0) if param != "respiratory_rate" else round(val, 1)

        return readings


def get_ventilator_scenario(scenario_name: str) -> VentilatorTrajectory:
    """Factory for standard mechanical ventilator profiles."""
    clean = scenario_name.strip().lower()

    if clean in ("no_vent", "none", "spontaneous", "off"):
        return VentilatorTrajectory(
            name="No Ventilation",
            mode="SPONT",
            verdict="Patient breathing spontaneously without invasive mechanical support",
            targets={
                "fio2": VentTarget(start=21.0, end=21.0),
                "peep": VentTarget(start=0.0, end=0.0),
                "tidal_volume": VentTarget(start=0.0, end=0.0),
                "respiratory_rate": VentTarget(start=0.0, end=0.0),
                "peak_pressure": VentTarget(start=0.0, end=0.0),
            },
        )

    elif clean in ("moderate", "standard", "moderate_vent"):
        return VentilatorTrajectory(
            name="Moderate Ventilation",
            mode="VC",
            verdict="Standard volume-controlled mechanical ventilation",
            targets={
                "fio2": VentTarget(start=35.0, end=40.0, noise_std_percent=0.0),
                "peep": VentTarget(start=6.0, end=8.0, noise_std_percent=0.01),
                "tidal_volume": VentTarget(start=500.0, end=500.0, noise_std_percent=0.01),
                "respiratory_rate": VentTarget(start=14.0, end=16.0, noise_std_percent=0.01),
                "peak_pressure": VentTarget(start=20.0, end=22.0, noise_std_percent=0.015),
            },
        )

    elif clean in ("severe", "ards", "severe_ards", "critical"):
        return VentilatorTrajectory(
            name="Severe ARDS (Lung-Protective)",
            mode="PC",
            verdict="Severe Acute Respiratory Distress Syndrome (ARDS) on lung-protective pressure ventilation",
            targets={
                "fio2": VentTarget(start=65.0, end=80.0, noise_std_percent=0.0),
                "peep": VentTarget(start=12.0, end=14.0, noise_std_percent=0.01),
                "tidal_volume": VentTarget(start=420.0, end=400.0, noise_std_percent=0.01),
                "respiratory_rate": VentTarget(start=20.0, end=24.0, noise_std_percent=0.01),
                "peak_pressure": VentTarget(start=28.0, end=32.0, noise_std_percent=0.015),
            },
        )

    else:
        raise ValueError(
            f"Unknown ventilator scenario '{scenario_name}'. Supported: 'no_vent', 'moderate', 'severe'"
        )
