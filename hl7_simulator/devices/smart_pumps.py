"""
smart_pumps.py — Smart Infusion Pump Network Simulator
======================================================
Simulates ICU smart infusion pumps (B.Braun Space, BD Alaris, Fresenius Agilia)
emitting HL7 v2.5 ORU^R01 (IHE PCD-01 Infusion profile).

Monitored Infusion Classes:
  - Vasoactive agents: Norepinephrine, Epinephrine, Dopamine
  - Sedatives & Analgesics: Propofol, Fentanyl
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from .base_device import BaseDevice
from ..core.loinc_codes import LOINC
from ..core.message_builder import HL7Message, HL7MessageBuilder
from ..scenarios.pump_scenarios import PumpTrajectory, get_pump_scenario

logger = logging.getLogger("hl7_simulator.pumps")

PumpBrand = Literal["bbraun", "alaris", "fresenius"]

PUMP_BRAND_APP_NAMES = {
    "bbraun": "BBRAUN_SPACE",
    "alaris": "BD_ALARIS",
    "fresenius": "FRESENIUS_AGILIA",
}


@dataclass
class PumpInterpretation:
    """Clinical interpretation of active intravenous infusions."""
    norepinephrine: float
    epinephrine: float
    dopamine: float
    propofol: float
    fentanyl: float
    vasopressor_status: str
    sedation_status: str
    verdict: str
    findings: List[str] = field(default_factory=list)

    def format_text(self) -> str:
        """Render clinical infusion summary report."""
        lines = [
            "Smart Infusion Pump Interpretation:",
            f"  * Vasopressor Requirement : {self.vasopressor_status}",
            f"  * Sedation / Analgesia     : {self.sedation_status}",
            f"  * Active Infusions        : NE: {self.norepinephrine:.2f} ug/kg/min | Epi: {self.epinephrine:.2f} ug/kg/min | Propofol: {self.propofol:.1f} ug/kg/min | Fentanyl: {self.fentanyl:.0f} ug/h",
            f"  * Clinical Verdict        : {self.verdict}",
        ]
        return "\n".join(lines)


class SmartPumps(BaseDevice):
    """
    Simulates a network of smart infusion pumps at the patient bedside.

    Active Drugs:
      - Norepinephrine (LOINC 77137-8, mcg/kg/min)
      - Epinephrine (LOINC 2272-6, mcg/kg/min)
      - Dopamine (LOINC 2215-5, mcg/kg/min)
      - Propofol (LOINC 11451-2, mcg/kg/min)
      - Fentanyl (LOINC 11450-4, mcg/hr)
    """

    def __init__(
        self,
        bed_id: str = "ICU_BED_01",
        patient_id: str = "224606",
        brand: PumpBrand = "bbraun",
        scenario_name: str = "no_vaso",
        trajectory: Optional[PumpTrajectory] = None,
    ):
        brand_clean = brand.lower()
        if brand_clean not in PUMP_BRAND_APP_NAMES:
            brand_clean = "bbraun"

        app_name = PUMP_BRAND_APP_NAMES[brand_clean]
        super().__init__(
            device_id=f"{app_name}_{bed_id}",
            device_name=app_name,
            bed_id=bed_id,
            patient_id=patient_id,
        )
        self.brand = brand_clean
        self.trajectory = trajectory or get_pump_scenario(scenario_name)

    def set_scenario(self, scenario_name: str) -> None:
        """Switch current pump trajectory."""
        self.trajectory = get_pump_scenario(scenario_name)
        logger.info(f"[{self.device_name}] Switched pump scenario to: {self.trajectory.name}")

    def get_readings(self, progress: float = 0.0) -> Dict[str, float]:
        """Sample current infusion rates along the timeline."""
        return self.trajectory.sample(progress=progress, add_noise=True)

    @classmethod
    def interpret(cls, readings: Dict[str, float]) -> PumpInterpretation:
        """
        Expert clinical interpretation of vasoactive and sedative infusion support.
        """
        ne = readings.get("norepinephrine", 0.0)
        epi = readings.get("epinephrine", 0.0)
        dopa = readings.get("dopamine", 0.0)
        prop = readings.get("propofol", 0.0)
        fent = readings.get("fentanyl", 0.0)

        findings: List[str] = []

        # 1. Vasopressor Evaluation
        vaso_count = sum(1 for d in [ne, epi, dopa] if d > 0.001)

        if ne >= 0.30 or epi >= 0.20 or vaso_count >= 2:
            vaso_status = "Refractory Shock (High-dose / Dual Vasopressor Support)"
            findings.append("Refractory shock")
            findings.append("High vasopressor requirement")
        elif ne > 0.01 or epi > 0.01 or dopa > 0.1:
            vaso_status = f"Moderate Hemodynamic Support (NE: {ne:.2f} ug/kg/min)"
            findings.append("Moderate shock")
        else:
            vaso_status = "No Inotropic / Vasopressor Support (Hemodynamically Stable)"

        # 2. Sedation / Analgesia Evaluation
        if prop >= 60.0 or fent >= 120.0:
            sed_status = f"Deep Sedation & Analgesia (Propofol: {prop:.1f} ug/kg/min, Fentanyl: {fent:.0f} ug/h)"
            findings.append("Deep sedation")
        elif prop > 10.0 or fent > 25.0:
            sed_status = f"Moderate Conscious / Procedural Sedation (Propofol: {prop:.1f} ug/kg/min)"
            findings.append("Moderate sedation")
        else:
            sed_status = "Minimal / No Continuous Sedation"

        # 3. Overall Diagnostic Verdict
        if "Refractory shock" in findings:
            verdict = "CRITICAL - Refractory Shock"
        elif "Moderate shock" in findings:
            verdict = "HIGH - Moderate Shock"
        elif "Deep sedation" in findings:
            verdict = "ALERT - Deep Sedation / Mechanical Ventilation Support"
        else:
            verdict = "STABLE - Hemodynamically Stable"

        return PumpInterpretation(
            norepinephrine=ne,
            epinephrine=epi,
            dopamine=dopa,
            propofol=prop,
            fentanyl=fent,
            vasopressor_status=vaso_status,
            sedation_status=sed_status,
            verdict=verdict,
            findings=findings,
        )

    def sample_on_demand(
        self,
        progress: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> tuple[Dict[str, float], PumpInterpretation, HL7Message]:
        """Sample active infusion pumps on demand."""
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
        Format active infusion rates into standardized HL7 v2.5 ORU^R01 with INFUSION_PARAMS.
        """
        ts = timestamp or datetime.now()
        builder = HL7MessageBuilder(
            patient_id=self.patient_id,
            bed_id=self.bed_id,
            sending_application=self.device_name,
            sending_facility=self.bed_id,
            receiving_application="ICU_GUARD",
            receiving_facility="HOSPITAL_CAIRO",
            panel_id="INFUSION_PARAMS",
            timestamp=ts,
        )

        mapping = [
            ("norepinephrine", LOINC.NORADRENALINE_RATE),
            ("epinephrine", LOINC.EPINEPHRINE_RATE),
            ("dopamine", LOINC.DOPAMINE_RATE),
            ("propofol", LOINC.PROPOFOL_RATE),
            ("fentanyl", LOINC.FENTANYL_RATE),
        ]

        for key, loinc_code in mapping:
            if key in readings:
                builder.add_observation(loinc_code, readings[key], obs_time=ts)

        return builder.build()
