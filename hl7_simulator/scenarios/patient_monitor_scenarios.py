"""
patient_monitor_scenarios.py — Telemetry Clinical Trajectories
================================================================
Defines clinical scenarios and trajectory profiles for patient monitors:
1. Stable Patient (euvolemic, normal vitals)
2. Deteriorating Patient (progressive respiratory/circulatory decline)
3. Critical Patient (Septic Shock / Acute Hypoperfusion)
4. Cohort-derived profile (loaded from multilabel_cohort.csv)
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("hl7_simulator.scenarios")


@dataclass
class VitalTarget:
    """Target range or endpoints for a specific vital sign."""
    start: float
    end: float
    noise_std_percent: float = 0.012


class PatientTrajectory:
    """
    Computes interpolated vitals across a 0.0 -> 1.0 progress timeline.
    """

    def __init__(self, name: str, targets: Dict[str, VitalTarget]):
        self.name = name
        self.targets = targets

    def sample(self, progress: float, add_noise: bool = True) -> Dict[str, float]:
        """Interpolate all vitals for given timeline progress (0.0 to 1.0)."""
        p = max(0.0, min(1.0, progress))
        readings: Dict[str, float] = {}

        for vital, target in self.targets.items():
            base_val = target.start + (target.end - target.start) * p
            if add_noise and target.noise_std_percent > 0:
                import random
                noise = random.gauss(0, base_val * target.noise_std_percent)
                val = base_val + noise
            else:
                val = base_val

            # Special clinical clamping
            if vital in ("heart_rate", "respiration_rate"):
                val = max(10.0, min(250.0, val))
            elif vital == "spo2":
                val = max(50.0, min(100.0, val))
            elif vital == "temperature":
                val = max(30.0, min(43.0, val))
            elif vital in ("sbp", "dbp", "mean_bp"):
                val = max(20.0, min(300.0, val))

            readings[vital] = round(val, 2)

        # Enforce consistency: MAP = DBP + (SBP - DBP)/3 if not explicitly diverging
        if "sbp" in readings and "dbp" in readings and "mean_bp" not in self.targets:
            readings["mean_bp"] = round(readings["dbp"] + (readings["sbp"] - readings["dbp"]) / 3.0, 2)

        return readings


def get_scenario_trajectory(scenario_name: str) -> PatientTrajectory:
    """
    Factory for standard predefined clinical monitor scenarios.
    """
    clean_name = scenario_name.strip().lower()

    if clean_name == "stable":
        return PatientTrajectory(
            name="Stable Patient",
            targets={
                "heart_rate": VitalTarget(start=78.0, end=78.0, noise_std_percent=0.015),
                "sbp": VitalTarget(start=120.0, end=120.0, noise_std_percent=0.015),
                "dbp": VitalTarget(start=80.0, end=80.0, noise_std_percent=0.015),
                "mean_bp": VitalTarget(start=93.3, end=93.3, noise_std_percent=0.015),
                "respiration_rate": VitalTarget(start=16.0, end=16.0, noise_std_percent=0.02),
                "spo2": VitalTarget(start=98.0, end=98.0, noise_std_percent=0.005),
                "temperature": VitalTarget(start=37.0, end=37.0, noise_std_percent=0.003),
            },
        )

    elif clean_name == "deteriorating":
        return PatientTrajectory(
            name="Deteriorating Patient",
            targets={
                "heart_rate": VitalTarget(start=85.0, end=110.0, noise_std_percent=0.015),
                "sbp": VitalTarget(start=115.0, end=90.0, noise_std_percent=0.015),
                "dbp": VitalTarget(start=75.0, end=58.0, noise_std_percent=0.015),
                "mean_bp": VitalTarget(start=88.3, end=68.7, noise_std_percent=0.015),
                "respiration_rate": VitalTarget(start=18.0, end=30.0, noise_std_percent=0.02),
                "spo2": VitalTarget(start=96.0, end=88.0, noise_std_percent=0.008),
                "temperature": VitalTarget(start=37.2, end=38.4, noise_std_percent=0.003),
            },
        )

    elif clean_name in ("critical", "septic_shock", "septic"):
        return PatientTrajectory(
            name="Critical Septic Shock",
            targets={
                "heart_rate": VitalTarget(start=90.0, end=128.0, noise_std_percent=0.015),
                "sbp": VitalTarget(start=110.0, end=74.0, noise_std_percent=0.015),
                "dbp": VitalTarget(start=70.0, end=32.0, noise_std_percent=0.015),
                "mean_bp": VitalTarget(start=83.3, end=46.0, noise_std_percent=0.015),
                "respiration_rate": VitalTarget(start=20.0, end=34.0, noise_std_percent=0.02),
                "spo2": VitalTarget(start=94.0, end=83.0, noise_std_percent=0.008),
                "temperature": VitalTarget(start=37.5, end=39.4, noise_std_percent=0.003),
            },
        )

    else:
        raise ValueError(
            f"Unknown scenario '{scenario_name}'. Supported: 'stable', 'deteriorating', 'critical'"
        )


def load_cohort_patient_trajectory(
    cohort_csv_path: str | Path,
    patient_id: str = "224606",
) -> PatientTrajectory:
    """
    Loads initial and extreme vitals for a given patient from multilabel_cohort.csv.
    """
    csv_file = Path(cohort_csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Cohort CSV not found at: {csv_file}")

    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("patientunitstayid") == str(patient_id):
                # Extract mean, min, max
                def _get(col: str, fallback: float) -> float:
                    val = row.get(col, "")
                    try:
                        return float(val) if val != "" else fallback
                    except ValueError:
                        return fallback

                hr_mean = _get("heartrate_mean", 80.0)
                hr_max = _get("heartrate_max", hr_mean + 15)
                sbp_mean = _get("sbp_mean", 120.0)
                sbp_min = _get("sbp_min", sbp_mean - 20)
                dbp_mean = _get("dbp_mean", 75.0)
                dbp_min = _get("dbp_min", dbp_mean - 15)
                mbp_mean = _get("meanbp_mean", 85.0)
                mbp_min = _get("meanbp_min", mbp_mean - 18)
                resp_mean = _get("respiration_mean", 18.0)
                resp_max = _get("respiration_max", resp_mean + 6)
                sao2_mean = _get("sao2_mean", 97.0)
                sao2_min = _get("sao2_min", sao2_mean - 5)
                temp_mean = _get("temperature_mean", 37.0)
                temp_max = _get("temperature_max", 37.8)

                return PatientTrajectory(
                    name=f"Cohort Patient {patient_id}",
                    targets={
                        "heart_rate": VitalTarget(start=hr_mean, end=hr_max),
                        "sbp": VitalTarget(start=sbp_mean, end=sbp_min),
                        "dbp": VitalTarget(start=dbp_mean, end=dbp_min),
                        "mean_bp": VitalTarget(start=mbp_mean, end=mbp_min),
                        "respiration_rate": VitalTarget(start=resp_mean, end=resp_max),
                        "spo2": VitalTarget(start=sao2_mean, end=sao2_min),
                        "temperature": VitalTarget(start=temp_mean, end=temp_max),
                    },
                )

    raise ValueError(f"Patient ID {patient_id} not found in {csv_file}")
