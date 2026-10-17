"""
lab_scenarios.py — Central Laboratory Clinical Scenarios
=========================================================
Defines longitudinal and point-in-time clinical laboratory profiles:
1. Normal Labs (Baseline physiological homeostasis)
2. Renal Failure (Progressive Acute Kidney Injury — KDIGO Stage 2)
3. Sepsis Pattern (Leukocytosis, consumption thrombocytopenia, metabolic stress)
4. DIC Pattern (Overt Disseminated Intravascular Coagulation — ISTH criteria)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger("hl7_simulator.lab_scenarios")


@dataclass
class LabTarget:
    """Target endpoints for a laboratory analyte."""
    start: float
    end: float
    noise_std_percent: float = 0.01


class LabTrajectory:
    """Computes interpolated Laboratory samples across clinical time."""

    def __init__(self, name: str, verdict: str, targets: Dict[str, LabTarget]):
        self.name = name
        self.verdict = verdict
        self.targets = targets

    def sample(self, progress: float = 0.0, add_noise: bool = True) -> Dict[str, float]:
        p = max(0.0, min(1.0, progress))
        readings: Dict[str, float] = {}

        for analyte, target in self.targets.items():
            base_val = target.start + (target.end - target.start) * p
            if add_noise and target.noise_std_percent > 0:
                import random
                noise = random.gauss(0, base_val * target.noise_std_percent)
                val = base_val + noise
            else:
                val = base_val

            # Standard physiological clamping and decimal rounding
            if analyte in ("creatinine", "inr"):
                val = max(0.1, min(20.0, val))
                readings[analyte] = round(val, 2)
            elif analyte in ("bun", "wbc", "platelets", "hemoglobin", "glucose", "sodium", "potassium", "ptt"):
                if analyte in ("wbc", "hemoglobin", "potassium"):
                    val = max(0.5, min(150.0, val))
                    readings[analyte] = round(val, 1)
                else:
                    val = max(1.0, min(1000.0, val))
                    readings[analyte] = round(val, 1)

        return readings


def get_lab_scenario(scenario_name: str) -> LabTrajectory:
    """Factory for standard central lab profiles."""
    clean = scenario_name.strip().lower()

    if clean in ("normal", "baseline"):
        return LabTrajectory(
            name="Normal Laboratory Profile",
            verdict="Normal organ function and hematological indices",
            targets={
                "creatinine": LabTarget(start=0.9, end=0.9, noise_std_percent=0.01),
                "bun": LabTarget(start=14.0, end=14.0, noise_std_percent=0.01),
                "wbc": LabTarget(start=7.2, end=7.2, noise_std_percent=0.015),
                "platelets": LabTarget(start=250.0, end=250.0, noise_std_percent=0.01),
                "hemoglobin": LabTarget(start=14.0, end=14.0, noise_std_percent=0.01),
                "glucose": LabTarget(start=92.0, end=92.0, noise_std_percent=0.015),
                "sodium": LabTarget(start=140.0, end=140.0, noise_std_percent=0.005),
                "potassium": LabTarget(start=4.1, end=4.1, noise_std_percent=0.01),
                "inr": LabTarget(start=1.0, end=1.0, noise_std_percent=0.01),
                "ptt": LabTarget(start=29.0, end=29.0, noise_std_percent=0.01),
            },
        )

    elif clean in ("renal", "renal_failure", "aki"):
        return LabTrajectory(
            name="Renal Failure (AKI Stage 2)",
            verdict="Acute Kidney Injury Stage 2 (KDIGO) with nitrogen retention and hyperkalemia risk",
            targets={
                "creatinine": LabTarget(start=1.4, end=2.8, noise_std_percent=0.01),
                "bun": LabTarget(start=28.0, end=52.0, noise_std_percent=0.015),
                "wbc": LabTarget(start=8.5, end=9.8, noise_std_percent=0.015),
                "platelets": LabTarget(start=210.0, end=195.0, noise_std_percent=0.015),
                "hemoglobin": LabTarget(start=12.5, end=11.2, noise_std_percent=0.01),
                "glucose": LabTarget(start=110.0, end=135.0, noise_std_percent=0.02),
                "sodium": LabTarget(start=138.0, end=134.0, noise_std_percent=0.005),
                "potassium": LabTarget(start=4.4, end=5.3, noise_std_percent=0.01),
                "inr": LabTarget(start=1.1, end=1.2, noise_std_percent=0.01),
                "ptt": LabTarget(start=30.0, end=32.0, noise_std_percent=0.015),
            },
        )

    elif clean in ("sepsis", "sepsis_pattern", "infection"):
        return LabTrajectory(
            name="Sepsis Laboratory Pattern",
            verdict="Severe systemic infection with leukocytosis, consumption thrombocytopenia, and stress hyperglycemia",
            targets={
                "creatinine": LabTarget(start=1.1, end=1.8, noise_std_percent=0.015),
                "bun": LabTarget(start=18.0, end=34.0, noise_std_percent=0.02),
                "wbc": LabTarget(start=12.8, end=18.5, noise_std_percent=0.02),
                "platelets": LabTarget(start=165.0, end=95.0, noise_std_percent=0.02),
                "hemoglobin": LabTarget(start=11.5, end=9.8, noise_std_percent=0.015),
                "glucose": LabTarget(start=140.0, end=185.0, noise_std_percent=0.025),
                "sodium": LabTarget(start=137.0, end=135.0, noise_std_percent=0.005),
                "potassium": LabTarget(start=4.0, end=4.6, noise_std_percent=0.015),
                "inr": LabTarget(start=1.2, end=1.7, noise_std_percent=0.015),
                "ptt": LabTarget(start=33.0, end=44.0, noise_std_percent=0.02),
            },
        )

    elif clean in ("dic", "dic_pattern", "coagulopathy"):
        return LabTrajectory(
            name="Disseminated Intravascular Coagulation (DIC)",
            verdict="Overt DIC (ISTH criteria): Profound thrombocytopenia and severe consumption coagulopathy",
            targets={
                "creatinine": LabTarget(start=1.6, end=2.4, noise_std_percent=0.015),
                "bun": LabTarget(start=32.0, end=48.0, noise_std_percent=0.02),
                "wbc": LabTarget(start=15.0, end=21.0, noise_std_percent=0.025),
                "platelets": LabTarget(start=85.0, end=45.0, noise_std_percent=0.03),
                "hemoglobin": LabTarget(start=9.5, end=7.8, noise_std_percent=0.02),
                "glucose": LabTarget(start=160.0, end=190.0, noise_std_percent=0.02),
                "sodium": LabTarget(start=135.0, end=132.0, noise_std_percent=0.005),
                "potassium": LabTarget(start=4.3, end=4.9, noise_std_percent=0.015),
                "inr": LabTarget(start=1.8, end=2.5, noise_std_percent=0.02),
                "ptt": LabTarget(start=48.0, end=65.0, noise_std_percent=0.02),
            },
        )

    else:
        raise ValueError(
            f"Unknown Lab scenario '{scenario_name}'. Supported: 'normal', 'renal', 'sepsis', 'dic'"
        )
