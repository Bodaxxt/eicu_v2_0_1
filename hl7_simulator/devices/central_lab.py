"""
central_lab.py — Central Laboratory Information System (LIS) Simulator
======================================================================
Simulates hospital central laboratory analyzers (Roche Cobas 8000,
Abbott ARCHITECT c16000, Siemens Atellica Solution) emitting HL7 v2.5 ORU^R01.

Supported Protocols & Integrations:
  - HL7 v2.5 ORU^R01 (Standard LIS interface via MLLP)
  - FHIR REST API (Observation resource mapping)
  - SQL View (Direct EMR/HIS database integration)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from .base_device import BaseDevice
from ..core.loinc_codes import LOINC
from ..core.message_builder import HL7Message, HL7MessageBuilder
from ..scenarios.lab_scenarios import LabTrajectory, get_lab_scenario

logger = logging.getLogger("hl7_simulator.lab")

LabBrand = Literal["roche", "abbott", "siemens"]

LAB_BRAND_APP_NAMES = {
    "roche": "ROCHE_COBAS_8000",
    "abbott": "ABBOTT_ARCHITECT",
    "siemens": "SIEMENS_ATELLICA",
}


@dataclass
class LabInterpretation:
    """Clinical interpretation of a comprehensive central laboratory panel."""
    creatinine: float
    bun: float
    wbc: float
    platelets: float
    hemoglobin: float
    glucose: float
    sodium: float
    potassium: float
    inr: float
    ptt: float
    aki_stage: str
    bun_cr_ratio: float
    hematology_status: str
    coagulation_status: str
    electrolyte_status: str
    verdict: str
    findings: List[str] = field(default_factory=list)

    def format_text(self) -> str:
        """Render clinical laboratory interpretation as a structured report."""
        lines = [
            "Laboratory Clinical Interpretation:",
            f"  * Renal Function : {self.aki_stage} (Cr: {self.creatinine:.2f} mg/dL, BUN: {self.bun:.1f}, Ratio: {self.bun_cr_ratio:.1f})",
            f"  * Hematology     : {self.hematology_status} (WBC: {self.wbc:.1f} K/uL, Plt: {self.platelets:.1f} K/uL, Hb: {self.hemoglobin:.1f} g/dL)",
            f"  * Coagulation    : {self.coagulation_status} (INR: {self.inr:.2f}, PTT: {self.ptt:.1f} s)",
            f"  * Electrolytes   : {self.electrolyte_status} (Na: {self.sodium:.1f}, K: {self.potassium:.1f} mEq/L)",
            f"  * Glucose Status : {'Hyperglycemia' if self.glucose > 140 else 'Hypoglycemia' if self.glucose < 70 else 'Euglycemic'} ({self.glucose:.1f} mg/dL)",
            f"  * Clinical Verdict: {self.verdict}",
        ]
        return "\n".join(lines)


class CentralLab(BaseDevice):
    """
    Simulates a Central Laboratory Information System (LIS).

    Measures 10 Core ICU Analytes:
      - Creatinine (LOINC 2160-0)
      - BUN (LOINC 3094-0)
      - WBC (LOINC 6690-2)
      - Platelets (LOINC 777-3)
      - Hemoglobin (LOINC 718-7)
      - Glucose (LOINC 2345-7)
      - Sodium (LOINC 2951-2)
      - Potassium (LOINC 2823-3)
      - INR (LOINC 6301-6)
      - PTT (LOINC 14979-9)
    """

    def __init__(
        self,
        bed_id: str = "ICU_BED_01",
        patient_id: str = "224606",
        brand: LabBrand = "roche",
        scenario_name: str = "normal",
        trajectory: Optional[LabTrajectory] = None,
    ):
        brand_clean = brand.lower()
        if brand_clean not in LAB_BRAND_APP_NAMES:
            brand_clean = "roche"

        app_name = LAB_BRAND_APP_NAMES[brand_clean]
        super().__init__(
            device_id=f"{app_name}_{bed_id}",
            device_name=app_name,
            bed_id=bed_id,
            patient_id=patient_id,
        )
        self.brand = brand_clean
        self.trajectory = trajectory or get_lab_scenario(scenario_name)

    def set_scenario(self, scenario_name: str) -> None:
        """Switch current lab trajectory."""
        self.trajectory = get_lab_scenario(scenario_name)
        logger.info(f"[{self.device_name}] Switched lab scenario to: {self.trajectory.name}")

    def get_readings(self, progress: float = 0.0) -> Dict[str, float]:
        """Sample current lab panel along the clinical timeline."""
        return self.trajectory.sample(progress=progress, add_noise=True)

    @classmethod
    def interpret(cls, readings: Dict[str, float], baseline_creatinine: float = 1.0) -> LabInterpretation:
        """
        Expert clinical evaluation of laboratory findings:
        KDIGO AKI staging, ISTH DIC scoring, hematological abnormalities, and electrolytes.
        """
        cr = readings.get("creatinine", 1.0)
        bun = readings.get("bun", 15.0)
        wbc = readings.get("wbc", 7.0)
        plt = readings.get("platelets", 250.0)
        hb = readings.get("hemoglobin", 13.5)
        glu = readings.get("glucose", 95.0)
        na = readings.get("sodium", 140.0)
        k = readings.get("potassium", 4.1)
        inr = readings.get("inr", 1.0)
        ptt = readings.get("ptt", 30.0)

        findings: List[str] = []

        # 1. Renal / KDIGO AKI Staging
        ratio = round(bun / cr, 1) if cr > 0 else 15.0
        cr_mult = cr / max(0.5, baseline_creatinine)

        if cr >= 4.0 or cr_mult >= 3.0:
            aki = "AKI Stage 3 (KDIGO)"
            findings.append("Severe AKI Stage 3")
        elif cr >= 2.0 or cr_mult >= 2.0:
            aki = "AKI Stage 2 (KDIGO)"
            findings.append("AKI Stage 2")
        elif cr >= 1.5 or cr_mult >= 1.5:
            aki = "AKI Stage 1 (KDIGO)"
            findings.append("Mild AKI Stage 1")
        else:
            aki = "Normal Renal Function"

        # 2. Hematology
        hem_parts: List[str] = []
        if wbc > 12.0:
            hem_parts.append(f"Leukocytosis ({wbc:.1f} K/uL)")
            findings.append("Leukocytosis")
        elif wbc < 4.0:
            hem_parts.append(f"Leukopenia ({wbc:.1f} K/uL)")
            findings.append("Leukopenia")

        if plt < 50.0:
            hem_parts.append(f"Severe Thrombocytopenia ({plt:.0f} K/uL)")
            findings.append("Severe Thrombocytopenia")
        elif plt < 100.0:
            hem_parts.append(f"Moderate Thrombocytopenia ({plt:.0f} K/uL)")
            findings.append("Thrombocytopenia")
        elif plt < 150.0:
            hem_parts.append(f"Mild Thrombocytopenia ({plt:.0f} K/uL)")

        if hb < 7.0:
            hem_parts.append(f"Severe Anemia ({hb:.1f} g/dL, Transfusion threshold)")
            findings.append("Severe Anemia")
        elif hb < 10.0:
            hem_parts.append(f"Moderate Anemia ({hb:.1f} g/dL)")
            findings.append("Moderate Anemia")
        elif hb < 12.0:
            hem_parts.append(f"Mild Anemia ({hb:.1f} g/dL)")

        hematology_status = ", ".join(hem_parts) if hem_parts else "Normal Blood Counts"

        # 3. Coagulation / ISTH DIC Evaluation
        coag_parts: List[str] = []
        isth_score = 0
        if plt < 50.0:
            isth_score += 2
        elif plt < 100.0:
            isth_score += 1

        if inr >= 2.3:
            isth_score += 2
            coag_parts.append("Severe Coagulopathy (INR >= 2.3)")
            findings.append("Severe Coagulopathy")
        elif inr > 1.4:
            isth_score += 1
            coag_parts.append("Prolonged INR")
            findings.append("Coagulopathy")

        if ptt > 45.0:
            coag_parts.append(f"Prolonged PTT ({ptt:.1f}s)")
            findings.append("Prolonged PTT")

        if isth_score >= 4 or (plt < 60.0 and inr >= 2.0):
            coag_status = "Overt Disseminated Intravascular Coagulation (ISTH criteria)"
            findings.append("Overt DIC")
        elif coag_parts:
            coag_status = "; ".join(coag_parts)
        else:
            coag_status = "Normal Hemostasis Profile"

        # 4. Electrolytes
        elec_parts: List[str] = []
        if na < 135.0:
            elec_parts.append(f"Hyponatremia ({na:.1f})")
            findings.append("Hyponatremia")
        elif na > 145.0:
            elec_parts.append(f"Hypernatremia ({na:.1f})")
            findings.append("Hypernatremia")

        if k < 3.5:
            elec_parts.append(f"Hypokalemia ({k:.1f})")
            findings.append("Hypokalemia")
        elif k > 5.0:
            elec_parts.append(f"Hyperkalemia ({k:.1f})")
            findings.append("Hyperkalemia")

        electrolyte_status = ", ".join(elec_parts) if elec_parts else "Normal Serum Electrolytes"

        # 5. Diagnostic Overall Verdict
        if "Overt DIC" in findings:
            verdict = "CRITICAL - Overt DIC (ISTH criteria)"
        elif ("Leukocytosis" in findings or "Severe AKI Stage 3" in findings) and "Thrombocytopenia" in findings:
            verdict = "HIGH - Sepsis with Organ Dysfunction"
        elif "AKI Stage 2" in findings or "Severe AKI Stage 3" in findings:
            verdict = "WARNING - AKI Stage 2 (KDIGO)"
        elif findings:
            verdict = f"ALERT - Multiple Abnormalities ({len(findings)} findings)"
        else:
            verdict = "STABLE - Normal Organ Function"

        return LabInterpretation(
            creatinine=cr,
            bun=bun,
            wbc=wbc,
            platelets=plt,
            hemoglobin=hb,
            glucose=glu,
            sodium=na,
            potassium=k,
            inr=inr,
            ptt=ptt,
            aki_stage=aki,
            bun_cr_ratio=ratio,
            hematology_status=hematology_status,
            coagulation_status=coag_status,
            electrolyte_status=electrolyte_status,
            verdict=verdict,
            findings=findings,
        )

    def sample_on_demand(
        self,
        progress: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> tuple[Dict[str, float], LabInterpretation, HL7Message]:
        """Execute a single point-of-care or central lab blood draw."""
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
        Format lab analytes into standardized HL7 v2.5 ORU^R01 with CHEM_PANEL.
        """
        ts = timestamp or datetime.now()
        builder = HL7MessageBuilder(
            patient_id=self.patient_id,
            bed_id=self.bed_id,
            sending_application=self.device_name,
            sending_facility=self.bed_id,
            receiving_application="ICU_GUARD",
            receiving_facility="HOSPITAL_CAIRO",
            panel_id="CHEM_PANEL",
            timestamp=ts,
        )

        mapping = [
            ("creatinine", LOINC.CREATININE),
            ("bun", LOINC.BUN),
            ("wbc", LOINC.WBC),
            ("platelets", LOINC.PLATELETS),
            ("hemoglobin", LOINC.HEMOGLOBIN),
            ("glucose", LOINC.GLUCOSE),
            ("sodium", LOINC.SODIUM),
            ("potassium", LOINC.POTASSIUM),
            ("inr", LOINC.INR),
            ("ptt", LOINC.PTT),
        ]

        for key, loinc_code in mapping:
            if key in readings:
                builder.add_observation(loinc_code, readings[key], obs_time=ts)

        return builder.build()
