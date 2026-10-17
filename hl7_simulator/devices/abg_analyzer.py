"""
abg_analyzer.py — Arterial Blood Gas (ABG) Point-of-Care Simulator
===================================================================
Simulates bedside ABG analyzers (Radiometer ABL800, Roche Cobas b 123,
Instrumentation Lab GEM Premier 5000) emitting HL7 v2.5 ORU^R01.

Supported Protocols & Middleware:
  - ASTM 1394 / 1381 (Serial / Point-of-care laboratory standard)
  - POCT1-A (Point-of-Care Coordinated Network Standard)
  - HL7 v2.5 ORU^R01 (Laboratory Information System & Middleware integration)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from .base_device import BaseDevice
from ..core.loinc_codes import LOINC
from ..core.message_builder import HL7Message, HL7MessageBuilder
from ..scenarios.abg_scenarios import ABGTrajectory, get_abg_scenario

logger = logging.getLogger("hl7_simulator.abg")

ABGBrand = Literal["radiometer", "roche", "il_gem"]

ABG_BRAND_APP_NAMES = {
    "radiometer": "RADIOMETER_ABL800",
    "roche": "ROCHE_COBAS_B123",
    "il_gem": "IL_GEM_PREMIER",
}


@dataclass
class ABGInterpretation:
    """Clinical interpretation of an arterial blood gas result."""
    ph: float
    pao2: float
    paco2: float
    lactate: float
    ph_status: str
    oxygenation_status: str
    paco2_status: str
    lactate_status: str
    primary_disorder: str
    compensation: str
    verdict: str
    findings: List[str] = field(default_factory=list)

    def format_text(self) -> str:
        """Render clinical interpretation as human-readable clinical summary."""
        lines = [
            f"ABG Interpretation:",
            f"  * Acid-Base : {self.primary_disorder} (pH: {self.ph:.2f})",
            f"  * Ventilation: {self.compensation} (PaCO2: {self.paco2:.1f} mmHg)",
            f"  * Oxygenation: {self.oxygenation_status} (PaO2: {self.pao2:.1f} mmHg)",
            f"  * Perfusion  : {self.lactate_status} (Lactate: {self.lactate:.2f} mmol/L)",
            f"  * Verdict    : {self.verdict}",
        ]
        return "\n".join(lines)


class ABGAnalyzer(BaseDevice):
    """
    Simulates a point-of-care Arterial Blood Gas (ABG) analyzer.

    Measures:
      - pH (LOINC 2744-1)
      - PaO2 (LOINC 2703-7, mmHg)
      - PaCO2 (LOINC 2019-8, mmHg)
      - Lactate (LOINC 2524-7, mmol/L)
    """

    def __init__(
        self,
        bed_id: str = "ICU_BED_01",
        patient_id: str = "224606",
        brand: ABGBrand = "radiometer",
        scenario_name: str = "normal",
        trajectory: Optional[ABGTrajectory] = None,
    ):
        brand_clean = brand.lower()
        if brand_clean not in ABG_BRAND_APP_NAMES:
            brand_clean = "radiometer"

        app_name = ABG_BRAND_APP_NAMES[brand_clean]
        super().__init__(
            device_id=f"{app_name}_{bed_id}",
            device_name=app_name,
            bed_id=bed_id,
            patient_id=patient_id,
        )
        self.brand = brand_clean
        self.trajectory = trajectory or get_abg_scenario(scenario_name)

    def set_scenario(self, scenario_name: str) -> None:
        """Switch current ABG clinical trajectory."""
        self.trajectory = get_abg_scenario(scenario_name)
        logger.info(f"[{self.device_name}] Switched scenario to: {self.trajectory.name}")

    def get_readings(self, progress: float = 0.0) -> Dict[str, float]:
        """Sample current ABG parameters along the timeline."""
        return self.trajectory.sample(progress=progress, add_noise=True)

    @classmethod
    def interpret(cls, readings: Dict[str, float]) -> ABGInterpretation:
        """
        Expert clinical interpretation of ABG parameters:
        Determines acidosis/alkalosis, metabolic vs respiratory, oxygenation, and lactate elevation.
        """
        ph = readings.get("ph", 7.40)
        pao2 = readings.get("pao2", 95.0)
        paco2 = readings.get("paco2", 40.0)
        lactate = readings.get("lactate", 1.2)

        findings: List[str] = []

        # 1. Acid-Base Status
        if ph < 7.35:
            ph_status = "Acidosis"
        elif ph > 7.45:
            ph_status = "Alkalosis"
        else:
            ph_status = "Normal pH"

        # 2. Ventilation / PaCO2
        if paco2 > 45.0:
            paco2_status = "CO2 Retention (Hypoventilation / Hypercapnia)"
        elif paco2 < 35.0:
            paco2_status = "Hyperventilation (Hypocapnia)"
        else:
            paco2_status = "Adequate Alveolar Ventilation"

        # 3. Oxygenation / PaO2
        if pao2 < 60.0:
            oxygenation_status = "Severe Hypoxemia (Tissue Hypoxia Risk)"
            findings.append("Severe Hypoxemia")
        elif pao2 < 80.0:
            oxygenation_status = "Mild-to-Moderate Hypoxemia"
            findings.append("Hypoxemia")
        else:
            oxygenation_status = "Normal Arterial Oxygenation"

        # 4. Lactate / Hypoperfusion
        if lactate > 8.0:
            lactate_status = "Critical Lactic Acidosis (Refractory Shock)"
            findings.append("Critical Lactate")
        elif lactate > 4.0:
            lactate_status = "Severe Hyperlactatemia (Septic / Cardiogenic Shock Marker)"
            findings.append("Severe Shock Marker")
        elif lactate > 2.0:
            lactate_status = "Elevated Lactate (Occult Hypoperfusion)"
            findings.append("Elevated Lactate")
        else:
            lactate_status = "Normal Tissue Perfusion"

        # 5. Primary Disorder & Compensation
        if ph < 7.35:
            if paco2 > 45.0 and lactate <= 2.2:
                primary = "Primary Respiratory Acidosis"
                comp = "Uncompensated or acutely developing"
                verdict = "WARNING - Acute Respiratory Acidosis"
            elif lactate > 2.2 and paco2 <= 40.0:
                primary = "Primary Metabolic Acidosis (Lactic Acidosis)"
                comp = "Compensatory Hyperventilation" if paco2 < 35.0 else "Minimal respiratory compensation"
                verdict = "CRITICAL - Septic Shock" if lactate >= 4.0 else "WARNING - Metabolic Acidosis"
            elif paco2 > 45.0 and lactate > 2.2:
                primary = "Mixed Metabolic and Respiratory Acidosis"
                comp = "No effective compensation (Dual System Failure)"
                verdict = "CRITICAL - Mixed Cardiorespiratory Failure"
            else:
                primary = "Metabolic Acidosis"
                comp = "Evaluating"
                verdict = "ALERT - Acidosis"
        elif ph > 7.45:
            if paco2 < 35.0:
                primary = "Respiratory Alkalosis"
                comp = "Hyperventilation / Pain / Anxiety"
                verdict = "NOTICE - Respiratory Alkalosis"
            else:
                primary = "Metabolic Alkalosis"
                comp = "Renal or gastrointestinal loss"
                verdict = "NOTICE - Metabolic Alkalosis"
        else:
            if lactate > 2.2 or paco2 < 35.0 or paco2 > 45.0:
                primary = "Compensated Acid-Base Disturbance"
                comp = "Normal pH maintained via homeostatic buffers"
                verdict = "CAUTION - Compensated Disturbance"
            else:
                primary = "Normal Acid-Base Homeostasis"
                comp = "Normal physiological equilibrium"
                verdict = "STABLE - Normal Gas Exchange"

        return ABGInterpretation(
            ph=ph,
            pao2=pao2,
            paco2=paco2,
            lactate=lactate,
            ph_status=ph_status,
            oxygenation_status=oxygenation_status,
            paco2_status=paco2_status,
            lactate_status=lactate_status,
            primary_disorder=primary,
            compensation=comp,
            verdict=verdict,
            findings=findings,
        )

    def sample_on_demand(
        self,
        progress: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> tuple[Dict[str, float], ABGInterpretation, HL7Message]:
        """
        Execute a single on-demand arterial blood gas draw.
        Returns: (readings_dict, clinical_interpretation, hl7_message)
        """
        readings = self.get_readings(progress=progress)
        interp = self.interpret(readings)
        msg = self.to_hl7(readings, timestamp=timestamp)
        return readings, interp, msg

    def to_hl7(
        self,
        readings: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> HL7Message:
        """
        Format ABG measurements into HL7 v2.5 ORU^R01 message with ABG_PANEL.
        """
        ts = timestamp or datetime.now()
        builder = HL7MessageBuilder(
            patient_id=self.patient_id,
            bed_id=self.bed_id,
            sending_application=self.device_name,
            sending_facility=self.bed_id,
            receiving_application="ICU_GUARD",
            receiving_facility="HOSPITAL_CAIRO",
            panel_id="ABG_PANEL",
            timestamp=ts,
        )

        if "ph" in readings:
            builder.add_observation(LOINC.PH, readings["ph"], obs_time=ts)
        if "pao2" in readings:
            builder.add_observation(LOINC.PAO2, readings["pao2"], obs_time=ts)
        if "paco2" in readings:
            builder.add_observation(LOINC.PACO2, readings["paco2"], obs_time=ts)
        if "lactate" in readings:
            builder.add_observation(LOINC.LACTATE, readings["lactate"], obs_time=ts)

        return builder.build()
