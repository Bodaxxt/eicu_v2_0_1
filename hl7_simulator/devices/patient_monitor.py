"""
patient_monitor.py — Bedside Patient Monitor Simulator
======================================================
Simulates advanced ICU bedside monitors (Philips IntelliVue MX800,
GE CARESCAPE B850, Mindray BeneVision N22) emitting HL7 v2.5 ORU^R01.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional, Literal

from .base_device import BaseDevice
from ..core.loinc_codes import LOINC
from ..core.message_builder import HL7Message, HL7MessageBuilder
from ..scenarios.patient_monitor_scenarios import (
    PatientTrajectory,
    get_scenario_trajectory,
    load_cohort_patient_trajectory,
)

logger = logging.getLogger("hl7_simulator.monitor")

MonitorBrand = Literal["philips", "ge", "mindray"]

BRAND_APP_NAMES = {
    "philips": "PHILIPS_INTELLIVUE",
    "ge": "GE_CARESCAPE",
    "mindray": "MINDRAY_BENEVISION",
}


class PatientMonitor(BaseDevice):
    """
    Simulates a bedside ICU Patient Monitor.

    Emits 7 continuous vital signs:
      - Heart Rate (LOINC 8867-4)
      - Systolic Blood Pressure (LOINC 8480-6)
      - Diastolic Blood Pressure (LOINC 8462-4)
      - Mean Arterial Pressure (LOINC 8478-0)
      - Respiratory Rate (LOINC 9279-1)
      - Oxygen Saturation / SpO2 (LOINC 2708-6)
      - Core Body Temperature (LOINC 8310-5)
    """

    def __init__(
        self,
        bed_id: str = "ICU_BED_01",
        patient_id: str = "224606",
        brand: MonitorBrand = "philips",
        trajectory: Optional[PatientTrajectory] = None,
        scenario_name: str = "stable",
    ):
        brand_clean = brand.lower()
        if brand_clean not in BRAND_APP_NAMES:
            brand_clean = "philips"

        app_name = BRAND_APP_NAMES[brand_clean]
        super().__init__(
            device_id=f"{app_name}_{bed_id}",
            device_name=app_name,
            bed_id=bed_id,
            patient_id=patient_id,
        )
        self.brand = brand_clean
        self.trajectory = trajectory or get_scenario_trajectory(scenario_name)

    def set_scenario(self, scenario_name: str) -> None:
        """Switch current clinical trajectory."""
        self.trajectory = get_scenario_trajectory(scenario_name)
        logger.info(f"[{self.device_name}] Switched trajectory to: {self.trajectory.name}")

    def load_cohort_patient(self, cohort_csv_path: str, patient_id: str) -> None:
        """Load patient profile directly from eICU cohort dataset."""
        self.patient_id = str(patient_id)
        self.trajectory = load_cohort_patient_trajectory(cohort_csv_path, patient_id)
        logger.info(f"[{self.device_name}] Loaded eICU patient {patient_id} into monitor")

    def get_readings(self, progress: float = 0.0) -> Dict[str, float]:
        """
        Sample current 7 vitals along the trajectory.
        """
        return self.trajectory.sample(progress=progress, add_noise=True)

    def to_hl7(
        self,
        readings: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> HL7Message:
        """
        Transform readings dictionary into a standardized HL7 v2.5 ORU^R01 message.
        """
        ts = timestamp or datetime.now()
        builder = HL7MessageBuilder(
            patient_id=self.patient_id,
            bed_id=self.bed_id,
            sending_application=self.device_name,
            sending_facility=self.bed_id,
            receiving_application="ICU_GUARD",
            receiving_facility="HOSPITAL_CAIRO",
            panel_id="TELEMETRY_PANEL",
            timestamp=ts,
        )

        # 1. Heart Rate
        if "heart_rate" in readings:
            builder.add_observation(LOINC.HEART_RATE, readings["heart_rate"], obs_time=ts)

        # 2. Systolic BP
        if "sbp" in readings:
            builder.add_observation(LOINC.SYSTOLIC_BP, readings["sbp"], obs_time=ts)

        # 3. Diastolic BP
        if "dbp" in readings:
            builder.add_observation(LOINC.DIASTOLIC_BP, readings["dbp"], obs_time=ts)

        # 4. Mean BP (MAP)
        if "mean_bp" in readings:
            builder.add_observation(LOINC.MEAN_BP, readings["mean_bp"], obs_time=ts)

        # 5. Respiratory Rate
        if "respiration_rate" in readings:
            builder.add_observation(LOINC.RESP_RATE, readings["respiration_rate"], obs_time=ts)

        # 6. SpO2
        if "spo2" in readings:
            builder.add_observation(LOINC.OXYGEN_SAT, readings["spo2"], obs_time=ts)

        # 7. Temperature
        if "temperature" in readings:
            builder.add_observation(LOINC.TEMPERATURE, readings["temperature"], obs_time=ts)

        return builder.build()
