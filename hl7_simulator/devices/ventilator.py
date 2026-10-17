"""
ventilator.py — Mechanical Ventilator Simulator
================================================
Simulates ICU mechanical ventilators (Draeger Evita V800, Hamilton-C6,
Puritan Bennett 980) emitting HL7 v2.5 ORU^R01.

Supported Protocols & Interfaces:
  - HL7 v2.5 ORU^R01 (VENTILATOR_PARAMS panel)
  - Draeger Infinity Gateway (HL7 / Medibus integration)
  - RS-232 / Serial to IP bridge
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from .base_device import BaseDevice
from ..core.loinc_codes import LOINC
from ..core.message_builder import HL7Message, HL7MessageBuilder
from ..scenarios.ventilator_scenarios import VentilatorTrajectory, get_ventilator_scenario

logger = logging.getLogger("hl7_simulator.ventilator")

VentBrand = Literal["draeger", "hamilton", "puritan"]

VENT_BRAND_APP_NAMES = {
    "draeger": "DRAEGER_EVITA",
    "hamilton": "HAMILTON_MEDICAL",
    "puritan": "PURITAN_BENNETT_980",
}


@dataclass
class VentilatorInterpretation:
    """Clinical interpretation of mechanical ventilator mechanics and support."""
    mode: str
    fio2: float
    peep: float
    tidal_volume: float
    respiratory_rate: float
    peak_pressure: float
    oxygenation_support: str
    lung_protective_status: str
    airway_pressure_status: str
    verdict: str
    findings: List[str] = field(default_factory=list)

    def format_text(self) -> str:
        """Render clinical ventilation summary report."""
        lines = [
            "Mechanical Ventilator Interpretation:",
            f"  * Ventilation Mode       : {self.mode}",
            f"  * Oxygenation Support    : {self.oxygenation_support} (FiO2: {self.fio2:.0f}%, PEEP: {self.peep:.1f} cmH2O)",
            f"  * Mechanics & Strategy   : {self.lung_protective_status} (TV: {self.tidal_volume:.0f} mL, RR: {self.respiratory_rate:.0f}/min)",
            f"  * Airway Pressure        : {self.airway_pressure_status} (PIP: {self.peak_pressure:.1f} cmH2O)",
            f"  * Clinical Verdict       : {self.verdict}",
        ]
        return "\n".join(lines)


class Ventilator(BaseDevice):
    """
    Simulates an invasive mechanical ventilator.

    Monitored Parameters:
      - Ventilation Mode (e.g. VC, PC, SPONT)
      - FiO2 (LOINC 3150-0, %)
      - PEEP (LOINC 76248-4, cmH2O)
      - Tidal Volume (LOINC 76222-9, mL)
      - Respiratory Rate (LOINC 9279-1, /min)
      - Peak Inspiratory Pressure (LOINC 76251-8, cmH2O)
    """

    def __init__(
        self,
        bed_id: str = "ICU_BED_01",
        patient_id: str = "224606",
        brand: VentBrand = "draeger",
        scenario_name: str = "no_vent",
        trajectory: Optional[VentilatorTrajectory] = None,
    ):
        brand_clean = brand.lower()
        if brand_clean not in VENT_BRAND_APP_NAMES:
            brand_clean = "draeger"

        app_name = VENT_BRAND_APP_NAMES[brand_clean]
        super().__init__(
            device_id=f"{app_name}_{bed_id}",
            device_name=app_name,
            bed_id=bed_id,
            patient_id=patient_id,
        )
        self.brand = brand_clean
        self.trajectory = trajectory or get_ventilator_scenario(scenario_name)

    def set_scenario(self, scenario_name: str) -> None:
        """Switch current ventilation trajectory."""
        self.trajectory = get_ventilator_scenario(scenario_name)
        logger.info(f"[{self.device_name}] Switched ventilator scenario to: {self.trajectory.name}")

    def get_readings(self, progress: float = 0.0) -> Dict[str, Any]:
        """Sample current ventilator parameters along the timeline."""
        return self.trajectory.sample(progress=progress, add_noise=True)

    @classmethod
    def interpret(cls, readings: Dict[str, Any]) -> VentilatorInterpretation:
        """
        Expert clinical evaluation of mechanical ventilation and ARDS severity.
        """
        mode = str(readings.get("mode", "SPONT"))
        fio2 = float(readings.get("fio2", 21.0))
        peep = float(readings.get("peep", 0.0))
        tv = float(readings.get("tidal_volume", 0.0))
        rr = float(readings.get("respiratory_rate", 0.0))
        pip = float(readings.get("peak_pressure", 0.0))

        findings: List[str] = []

        if mode == "SPONT" or (tv <= 1.0 and peep <= 1.0):
            return VentilatorInterpretation(
                mode="SPONT / Extubated",
                fio2=fio2,
                peep=peep,
                tidal_volume=tv,
                respiratory_rate=rr,
                peak_pressure=pip,
                oxygenation_support="Room Air / Spontaneous Breathing",
                lung_protective_status="Not Applicable (Spontaneous Breathing)",
                airway_pressure_status="Atmospheric",
                verdict="STABLE - Spontaneous Breathing",
                findings=["Spontaneous breathing"],
            )

        # 1. Oxygenation Support & PEEP
        if fio2 >= 65.0 or peep >= 12.0:
            o2_support = f"Severe Hypoxemia Support (High FiO2: {fio2:.0f}%, High PEEP: {peep:.1f} cmH2O)"
            findings.append("Severe ARDS")
            findings.append("High FiO2 requirement")
            findings.append("High PEEP")
        elif fio2 >= 40.0 or peep >= 8.0:
            o2_support = f"Moderate Ventilation Support (FiO2: {fio2:.0f}%, PEEP: {peep:.1f} cmH2O)"
            findings.append("Moderate ventilation support")
        else:
            o2_support = f"Low Ventilation Support (FiO2: {fio2:.0f}%, PEEP: {peep:.1f} cmH2O)"

        # 2. Lung-Protective Strategy (Low Tidal Volume ~4-6 ml/kg IBW ~ 350-450 mL)
        if 0 < tv <= 420.0:
            lung_prot = f"Lung-Protective Strategy (Low TV: {tv:.0f} mL ~6 mL/kg IBW)"
            findings.append("Lung-protective ventilation")
        elif tv > 550.0:
            lung_prot = f"High Tidal Volume ({tv:.0f} mL - Risk of Volutrauma)"
            findings.append("High tidal volume")
        else:
            lung_prot = f"Standard Tidal Volume ({tv:.0f} mL)"

        # 3. Airway Pressures
        if pip >= 30.0:
            pip_status = f"Elevated Peak Pressure ({pip:.1f} cmH2O - Barotrauma Risk / Stiff Lung)"
            findings.append("Elevated peak pressure")
        else:
            pip_status = f"Acceptable Airway Pressure ({pip:.1f} cmH2O)"

        # 4. Overall Clinical Verdict
        if "Severe ARDS" in findings:
            verdict = "CRITICAL - Severe ARDS"
        elif "Moderate ventilation support" in findings:
            verdict = "MODERATE - Standard Mechanical Ventilation"
        else:
            verdict = "STABLE - Minimal Mechanical Support"

        return VentilatorInterpretation(
            mode=mode,
            fio2=fio2,
            peep=peep,
            tidal_volume=tv,
            respiratory_rate=rr,
            peak_pressure=pip,
            oxygenation_support=o2_support,
            lung_protective_status=lung_prot,
            airway_pressure_status=pip_status,
            verdict=verdict,
            findings=findings,
        )

    def sample_on_demand(
        self,
        progress: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> tuple[Dict[str, Any], VentilatorInterpretation, HL7Message]:
        """Sample ventilator metrics on demand."""
        readings = self.get_readings(progress=progress)
        interp = self.interpret(readings)
        msg = self.to_hl7(readings, timestamp=timestamp)
        return readings, interp, msg

    def to_hl7(
        self,
        readings: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> HL7Message:
        """
        Format ventilator parameters into standardized HL7 v2.5 ORU^R01 with VENTILATOR_PARAMS.
        """
        ts = timestamp or datetime.now()
        builder = HL7MessageBuilder(
            patient_id=self.patient_id,
            bed_id=self.bed_id,
            sending_application=self.device_name,
            sending_facility=self.bed_id,
            receiving_application="ICU_GUARD",
            receiving_facility="HOSPITAL_CAIRO",
            panel_id="VENTILATOR_PARAMS",
            timestamp=ts,
        )

        # 1. Mode
        if "mode" in readings:
            mode_val = str(readings["mode"])
            builder.add_observation(LOINC.VENTILATOR_MODE, 1.0 if mode_val != "SPONT" else 0.0, obs_time=ts)

        # 2. FiO2
        if "fio2" in readings and readings["fio2"] > 0:
            builder.add_observation(LOINC.FIO2, float(readings["fio2"]), obs_time=ts)

        # 3. PEEP
        if "peep" in readings and readings["peep"] > 0:
            builder.add_observation(LOINC.PEEP, float(readings["peep"]), obs_time=ts)

        # 4. Tidal Volume
        if "tidal_volume" in readings and readings["tidal_volume"] > 0:
            builder.add_observation(LOINC.TIDAL_VOLUME, float(readings["tidal_volume"]), obs_time=ts)

        # 5. Respiratory Rate
        if "respiratory_rate" in readings and readings["respiratory_rate"] > 0:
            builder.add_observation(LOINC.RESP_RATE, float(readings["respiratory_rate"]), obs_time=ts)

        # 6. Peak Pressure
        if "peak_pressure" in readings and readings["peak_pressure"] > 0:
            builder.add_observation(LOINC.PEAK_PRESSURE, float(readings["peak_pressure"]), obs_time=ts)

        # Fallback if extubated / no parameters
        if not builder._observations:
            builder.add_observation(LOINC.FIO2, 21.0, obs_time=ts)

        return builder.build()
