"""
pump_scenarios.py — Smart Infusion Pump Clinical Scenarios
===========================================================
Defines infusion trajectories for critical care vasoactive & sedative infusions:
1. No Vasopressors (Stable hemodynamics, no support)
2. Moderate Support (Single vasopressor + moderate sedation)
3. High Support (Dual high-dose vasopressors + deep sedation / Refractory Shock)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger("hl7_simulator.pump_scenarios")


@dataclass
class PumpTarget:
    """Target endpoints for an infused drug."""
    start: float
    end: float
    noise_std_percent: float = 0.005


class PumpTrajectory:
    """Computes interpolated drug infusion rates across clinical time."""

    def __init__(self, name: str, verdict: str, targets: Dict[str, PumpTarget]):
        self.name = name
        self.verdict = verdict
        self.targets = targets

    def sample(self, progress: float = 0.0, add_noise: bool = True) -> Dict[str, float]:
        p = max(0.0, min(1.0, progress))
        readings: Dict[str, float] = {}

        for drug, target in self.targets.items():
            base_val = target.start + (target.end - target.start) * p
            if add_noise and target.noise_std_percent > 0 and base_val > 0:
                import random
                noise = random.gauss(0, base_val * target.noise_std_percent)
                val = max(0.0, base_val + noise)
            else:
                val = base_val

            if drug in ("norepinephrine", "epinephrine"):
                readings[drug] = round(val, 2)
            elif drug == "dopamine":
                readings[drug] = round(val, 1)
            elif drug == "propofol":
                readings[drug] = round(val, 1)
            elif drug == "fentanyl":
                readings[drug] = round(val, 0)

        return readings


def get_pump_scenario(scenario_name: str) -> PumpTrajectory:
    """Factory for standard smart pump profiles."""
    clean = scenario_name.strip().lower()

    if clean in ("no_vaso", "none", "stable"):
        return PumpTrajectory(
            name="No Vasopressors",
            verdict="Hemodynamically stable without inotropic or vasopressor support",
            targets={
                "norepinephrine": PumpTarget(start=0.0, end=0.0),
                "epinephrine": PumpTarget(start=0.0, end=0.0),
                "dopamine": PumpTarget(start=0.0, end=0.0),
                "propofol": PumpTarget(start=0.0, end=0.0),
                "fentanyl": PumpTarget(start=0.0, end=0.0),
            },
        )

    elif clean in ("moderate", "moderate_support"):
        return PumpTrajectory(
            name="Moderate Hemodynamic Support",
            verdict="Moderate vasodilatory shock requiring single vasopressor titration and sedation",
            targets={
                "norepinephrine": PumpTarget(start=0.04, end=0.10, noise_std_percent=0.01),
                "epinephrine": PumpTarget(start=0.0, end=0.0),
                "dopamine": PumpTarget(start=0.0, end=0.0),
                "propofol": PumpTarget(start=35.0, end=50.0, noise_std_percent=0.01),
                "fentanyl": PumpTarget(start=50.0, end=50.0, noise_std_percent=0.0),
            },
        )

    elif clean in ("high", "high_support", "refractory", "septic"):
        return PumpTrajectory(
            name="High Vasopressor Support (Refractory Shock)",
            verdict="Refractory septic shock requiring escalating dual vasopressors and deep sedation",
            targets={
                "norepinephrine": PumpTarget(start=0.20, end=0.50, noise_std_percent=0.01),
                "epinephrine": PumpTarget(start=0.05, end=0.30, noise_std_percent=0.01),
                "dopamine": PumpTarget(start=0.0, end=0.0),
                "propofol": PumpTarget(start=50.0, end=75.0, noise_std_percent=0.01),
                "fentanyl": PumpTarget(start=100.0, end=150.0, noise_std_percent=0.01),
            },
        )

    else:
        raise ValueError(
            f"Unknown pump scenario '{scenario_name}'. Supported: 'no_vaso', 'moderate', 'high'"
        )
