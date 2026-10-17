"""
vital_signs.py — Vital Signs Telemetry Simulation Scenario
============================================================
Simulates a patient on a Philips IntelliVue bedside monitor
transitioning from stable condition to acute septic shock / deterioration.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Generator

from .base_scenario import BaseScenario
from ..core.message_builder import HL7Message, HL7MessageBuilder


class VitalSignsScenario(BaseScenario):
    """
    Simulates a sequence of vital sign frames from a bedside patient monitor.

    Progression:
        Frame 1: Baseline stable
        Frame 2: Mild tachycardia & borderline hypotension
        Frame 3: Tachycardia + Hypoperfusion (MAP 58)
        Frame 4: Septic Shock / Respiratory Distress (MAP 46, SpO2 86%, HR 118)
    """

    STAGES = [
        # (HR, SBP, DBP, MAP, RR, SpO2, Temp)
        (78.0, 122.0, 78.0, 92.0, 16.0, 98.0, 37.0),   # Baseline Stable
        (96.0, 108.0, 68.0, 81.0, 20.0, 95.0, 38.1),   # Early SIRS / Fever
        (110.0, 88.0, 52.0, 64.0, 26.0, 91.0, 38.6),   # Decompensating
        (118.0, 72.0, 42.0, 46.0, 32.0, 84.0, 39.2),   # Severe Septic Shock
    ]

    def generate_messages(self) -> Generator[HL7Message, None, None]:
        base_time = datetime.now() - timedelta(minutes=15 * len(self.STAGES))

        for idx, (hr, sbp, dbp, mean_bp, rr, spo2, temp) in enumerate(self.STAGES):
            t = base_time + timedelta(minutes=15 * idx)
            msg = HL7MessageBuilder.monitor_message(
                patient_id=self.patient_id,
                bed_id=self.bed_id,
                heart_rate=hr,
                sbp=sbp,
                dbp=dbp,
                map_bp=mean_bp,
                resp_rate=rr,
                spo2=spo2,
                temperature=temp,
                timestamp=t,
            )
            yield msg
