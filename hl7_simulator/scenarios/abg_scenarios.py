"""
abg_scenarios.py — Arterial Blood Gas (ABG) Clinical Scenarios
==============================================================
Defines physiological arterial blood gas profiles:
1. Normal ABG (Homeostasis)
2. Metabolic Acidosis (Lactic acid accumulation / hypoperfusion)
3. Respiratory Failure (Type II Hypercapnic respiratory failure)
4. Septic Shock (Severe mixed lactic acidosis + hyperventilation compensation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger("hl7_simulator.abg_scenarios")


@dataclass
class ABGTarget:
    """Target endpoints for an ABG parameter."""
    start: float
    end: float
    noise_std_percent: float = 0.008


class ABGTrajectory:
    """Computes interpolated ABG samples across a clinical observation window."""

    def __init__(self, name: str, verdict: str, targets: Dict[str, ABGTarget]):
        self.name = name
        self.verdict = verdict
        self.targets = targets

    def sample(self, progress: float = 0.0, add_noise: bool = True) -> Dict[str, float]:
        p = max(0.0, min(1.0, progress))
        readings: Dict[str, float] = {}

        for param, target in self.targets.items():
            base_val = target.start + (target.end - target.start) * p
            if add_noise and target.noise_std_percent > 0:
                import random
                noise = random.gauss(0, base_val * target.noise_std_percent)
                val = base_val + noise
            else:
                val = base_val

            # Physiological clamping
            if param == "ph":
                val = max(6.80, min(7.80, val))
                readings[param] = round(val, 2)
            elif param in ("pao2", "paco2"):
                val = max(20.0, min(250.0, val))
                readings[param] = round(val, 1)
            elif param == "lactate":
                val = max(0.2, min(30.0, val))
                readings[param] = round(val, 2)

        return readings


def get_abg_scenario(scenario_name: str) -> ABGTrajectory:
    """Factory for standard clinical ABG profiles."""
    clean = scenario_name.strip().lower()

    if clean in ("normal", "stable"):
        return ABGTrajectory(
            name="Normal ABG",
            verdict="Normal gas exchange and tissue perfusion",
            targets={
                "ph": ABGTarget(start=7.40, end=7.40, noise_std_percent=0.002),
                "pao2": ABGTarget(start=95.0, end=95.0, noise_std_percent=0.01),
                "paco2": ABGTarget(start=40.0, end=40.0, noise_std_percent=0.01),
                "lactate": ABGTarget(start=1.2, end=1.2, noise_std_percent=0.02),
            },
        )

    elif clean in ("acidosis", "metabolic_acidosis", "metabolic"):
        return ABGTrajectory(
            name="Metabolic Acidosis",
            verdict="Severe metabolic acidosis with hypoperfusion shock",
            targets={
                "ph": ABGTarget(start=7.36, end=7.25, noise_std_percent=0.003),
                "pao2": ABGTarget(start=90.0, end=80.0, noise_std_percent=0.01),
                "paco2": ABGTarget(start=38.0, end=35.0, noise_std_percent=0.01),
                "lactate": ABGTarget(start=2.1, end=4.8, noise_std_percent=0.02),
            },
        )

    elif clean in ("respiratory", "respiratory_failure", "copd"):
        return ABGTrajectory(
            name="Respiratory Failure",
            verdict="Type 2 hypercapnic respiratory failure",
            targets={
                "ph": ABGTarget(start=7.34, end=7.28, noise_std_percent=0.003),
                "pao2": ABGTarget(start=75.0, end=60.0, noise_std_percent=0.015),
                "paco2": ABGTarget(start=46.0, end=55.0, noise_std_percent=0.01),
                "lactate": ABGTarget(start=1.8, end=3.2, noise_std_percent=0.02),
            },
        )

    elif clean in ("septic", "septic_shock", "critical"):
        return ABGTrajectory(
            name="Critical Septic Shock",
            verdict="Critical lactic acidosis, severe tissue hypoperfusion, and septic shock",
            targets={
                "ph": ABGTarget(start=7.32, end=7.15, noise_std_percent=0.004),
                "pao2": ABGTarget(start=82.0, end=65.0, noise_std_percent=0.015),
                "paco2": ABGTarget(start=34.0, end=30.0, noise_std_percent=0.01),
                "lactate": ABGTarget(start=3.5, end=8.5, noise_std_percent=0.02),
            },
        )

    else:
        raise ValueError(
            f"Unknown ABG scenario '{scenario_name}'. Supported: 'normal', 'acidosis', 'respiratory', 'septic'"
        )
