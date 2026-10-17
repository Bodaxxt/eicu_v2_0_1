"""
ICU Guard v4.2 — Organ System Detectors
=======================================
Implements 5 evidence-based physiological organ failure detectors:
1. RespiratoryDetector     (Berlin ARDS Definition 2012)
2. HemodynamicDetector     (Shock Index & SSC Perfusion Guidelines)
3. RenalDetector           (KDIGO 2012 AKI Staging)
4. NeurologicalDetector    (Glasgow Coma Scale Spectrum)
5. SepsisDetector          (SIRS Criteria & SSC 2021 Septic Shock)

Each detector evaluates patient variables and outputs an injury grade from 0 (Normal) to 3 (Severe/Failure).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math
import logging

from severity_agent.config import (
    RESPIRATORY_CONFIG,
    HEMODYNAMIC_CONFIG,
    RENAL_CONFIG,
    NEUROLOGICAL_CONFIG,
    SEPSIS_CONFIG,
    HEPATIC_CONFIG,
    COAGULATION_CONFIG,
    METABOLIC_CONFIG,
    ENDOCRINE_CONFIG,
    HEMATOLOGIC_CONFIG,
    NUTRITIONAL_CONFIG
)

logger = logging.getLogger(__name__)


@dataclass
class OrganAssessment:
    """Standardized physiological assessment for a single organ system."""
    organ_name: str
    grade: int  # 0: Normal, 1: Mild, 2: Moderate, 3: Severe/Failure
    description: str
    clinical_evidence: List[str] = field(default_factory=list)
    guideline_reference: str = ""
    missing_indicators: List[str] = field(default_factory=list)
    suggested_action: str = ""

    @property
    def is_compromised(self) -> bool:
        """Indicates whether the organ system shows any non-trivial injury."""
        return self.grade >= 1

    @property
    def is_critical(self) -> bool:
        """Indicates acute severe organ failure."""
        return self.grade >= 2


class BaseOrganDetector(ABC):
    """Abstract base class for all organ system detectors."""

    def __init__(self, name: str, guideline: str):
        self.name = name
        self.guideline = guideline

    @abstractmethod
    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        """
        Evaluate patient vital signs and laboratory measurements.
        
        Args:
            vitals: Dictionary containing raw patient physiological features.
            
        Returns:
            OrganAssessment containing the injury grade and clinical rationale.
        """
        pass

    @staticmethod
    def _get_val(vitals: Dict[str, Any], *keys: str) -> Optional[float]:
        """Safely extract the first available numeric value from multiple possible keys."""
        for k in keys:
            if k in vitals:
                val = vitals[k]
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
        return None


class RespiratoryDetector(BaseOrganDetector):
    """
    Evaluates pulmonary oxygenation, ventilation reserve, and ARDS criteria.
    Guideline: Berlin Definition for ARDS (2012) & Hypoxemia Protocols.
    """

    def __init__(self):
        super().__init__(name="Respiratory", guideline="Berlin ARDS Definition 2012")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        # Retrieve relevant features
        sao2 = self._get_val(vitals, 'sao2_min', 'sao2_mean', 'sao2', 'o2sat')
        pao2 = self._get_val(vitals, 'pao2_min', 'pao2_mean', 'pao2')
        rr = self._get_val(vitals, 'resprate_max', 'respiration_rate', 'resprate_mean', 'resprate', 'resprate_min')
        rr_min = self._get_val(vitals, 'resprate_min')
        o2_reserve = self._get_val(vitals, 'o2_reserve')

        if sao2 is None:
            missing.append("sao2")
        if pao2 is None:
            missing.append("pao2")
        if rr is None and rr_min is None:
            missing.append("respiration_rate")

        cfg = RESPIRATORY_CONFIG

        # Grade 3: Severe hypoxemic failure / impending respiratory arrest / apnea
        if (sao2 is not None and sao2 < cfg['sao2_grade3']) or \
           (pao2 is not None and pao2 < cfg['pao2_grade3']) or \
           (rr is not None and (rr >= cfg['rr_high_grade3'] or rr < cfg['rr_low_grade3'])) or \
           (rr_min is not None and rr_min < cfg['rr_low_grade3']):
            grade = 3
            if sao2 is not None and sao2 < cfg['sao2_grade3']:
                evidence.append(f"Severe hypoxemia (SaO2 {sao2:.1f}% < {cfg['sao2_grade3']}%)")
            if pao2 is not None and pao2 < cfg['pao2_grade3']:
                evidence.append(f"Severe gas exchange compromise (PaO2 {pao2:.1f} mmHg < {cfg['pao2_grade3']} mmHg)")
            if rr is not None and rr >= cfg['rr_high_grade3']:
                evidence.append(f"Severe tachypnea / work of breathing (RR {rr:.1f} >= {cfg['rr_high_grade3']})")
            if (rr is not None and rr < cfg['rr_low_grade3']) or (rr_min is not None and rr_min < cfg['rr_low_grade3']):
                val = rr_min if rr_min is not None and rr_min < cfg['rr_low_grade3'] else rr
                evidence.append(f"Respiratory exhaustion / bradypnea (RR {val:.1f} < {cfg['rr_low_grade3']})")

        # Grade 2: Moderate ARDS / significant oxygenation deficit
        elif (sao2 is not None and sao2 < cfg['sao2_grade2']) or \
             (pao2 is not None and pao2 < cfg['pao2_grade2']) or \
             (rr is not None and rr >= cfg['rr_high_grade2']) or \
             (o2_reserve is not None and o2_reserve < cfg['o2_reserve_low']):
            grade = 2
            if sao2 is not None and sao2 < cfg['sao2_grade2']:
                evidence.append(f"Moderate hypoxemia (SaO2 {sao2:.1f}% < {cfg['sao2_grade2']}%)")
            if pao2 is not None and pao2 < cfg['pao2_grade2']:
                evidence.append(f"Moderate hypoxemic ARDS (PaO2 {pao2:.1f} mmHg < {cfg['pao2_grade2']} mmHg)")
            if rr is not None and rr >= cfg['rr_high_grade2']:
                evidence.append(f"Marked tachypnea (RR {rr:.1f} >= {cfg['rr_high_grade2']})")
            if o2_reserve is not None and o2_reserve < cfg['o2_reserve_low']:
                evidence.append(f"Severely depleted physiological O2 reserve ({o2_reserve:.1f} < {cfg['o2_reserve_low']})")

        # Grade 1: Mild hypoxemia or mild tachypnea
        elif (sao2 is not None and sao2 < cfg['sao2_grade1']) or \
             (pao2 is not None and pao2 < cfg['pao2_grade1']) or \
             (rr is not None and rr >= cfg['rr_high_grade1']):
            grade = 1
            if sao2 is not None and sao2 < cfg['sao2_grade1']:
                evidence.append(f"Mild hypoxemia (SaO2 {sao2:.1f}% < {cfg['sao2_grade1']}%)")
            if pao2 is not None and pao2 < cfg['pao2_grade1']:
                evidence.append(f"Mild gas exchange impairment (PaO2 {pao2:.1f} mmHg < {cfg['pao2_grade1']} mmHg)")
            if rr is not None and rr >= cfg['rr_high_grade1']:
                evidence.append(f"Mild tachypnea (RR {rr:.1f} >= {cfg['rr_high_grade1']})")
        else:
            evidence.append("Adequate oxygenation and respiratory mechanics within normal range.")

        descriptions = {
            0: "Normal Pulmonary Function",
            1: "Mild Respiratory Compromise / Hypoxemia",
            2: "Moderate Respiratory Failure / Acute Lung Injury",
            3: "Severe Hypoxemic Respiratory Failure (Impending Arrest / ARDS Stage 3)"
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing
        )


class HemodynamicDetector(BaseOrganDetector):
    """
    Evaluates systemic perfusion pressure, vasomotor stability, and shock states.
    Guideline: Surviving Sepsis Campaign (SSC 2021) & Shock Index Protocols.
    """

    def __init__(self):
        super().__init__(name="Hemodynamic", guideline="SSC 2021 & Shock Index Protocols")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        map_val = self._get_val(vitals, 'meanbp_min', 'meanbp_mean', 'meanbp', 'systemicmean')
        sbp = self._get_val(vitals, 'sbp_min', 'sbp_mean', 'systolicbp', 'sbp')
        sbp_max = self._get_val(vitals, 'sbp_max', 'systolicbp_max')
        hr = self._get_val(vitals, 'heartrate_max', 'heartrate_mean', 'heartrate')
        si = self._get_val(vitals, 'shock_index_max', 'shock_index')

        # Fallback calculation of Shock Index if missing
        if si is None and hr is not None and sbp is not None and sbp > 0:
            si = hr / sbp

        if map_val is None:
            missing.append("meanbp")
        if sbp is None and sbp_max is None:
            missing.append("sbp")
        if hr is None:
            missing.append("heartrate")

        cfg = HEMODYNAMIC_CONFIG

        # Grade 3: Severe uncompensated shock / cardiovascular collapse
        if (map_val is not None and map_val < cfg['map_grade3']) or \
           (sbp is not None and sbp < cfg['sbp_grade3']) or \
           (si is not None and si > cfg['shock_index_grade3']) or \
           (hr is not None and (hr >= cfg['hr_high_grade3'] or hr < cfg['hr_low_grade3'])):
            grade = 3
            if map_val is not None and map_val < cfg['map_grade3']:
                evidence.append(f"Profound hypotension (MAP {map_val:.1f} mmHg < {cfg['map_grade3']} mmHg)")
            if sbp is not None and sbp < cfg['sbp_grade3']:
                evidence.append(f"Refractory hypotension (SBP {sbp:.1f} mmHg < {cfg['sbp_grade3']} mmHg)")
            if si is not None and si > cfg['shock_index_grade3']:
                evidence.append(f"Critical shock index (SI {si:.2f} > {cfg['shock_index_grade3']})")
            if hr is not None and hr >= cfg['hr_high_grade3']:
                evidence.append(f"Extreme compensatory tachycardia (HR {hr:.1f} >= {cfg['hr_high_grade3']} bpm)")
            if hr is not None and hr < cfg['hr_low_grade3']:
                evidence.append(f"Severe bradycardia / impending asystole (HR {hr:.1f} < {cfg['hr_low_grade3']} bpm)")

        # Grade 2: Uncompensated shock / hypotension failing perfusion goals / Hypertensive crisis
        elif (map_val is not None and map_val < cfg['map_grade2']) or \
             (sbp is not None and sbp < cfg['sbp_grade2']) or \
             (si is not None and si > cfg['shock_index_grade2']) or \
             (hr is not None and hr >= cfg['hr_high_grade2']) or \
             (sbp_max is not None and sbp_max >= 180.0):
            grade = 2
            if sbp_max is not None and sbp_max >= 180.0:
                evidence.append(f"Hypertensive crisis / severe afterload elevation (SBP {sbp_max:.1f} >= 180 mmHg)")
            if map_val is not None and map_val < cfg['map_grade2']:
                evidence.append(f"Unmet SSC MAP perfusion target (MAP {map_val:.1f} mmHg < {cfg['map_grade2']} mmHg)")
            if sbp is not None and sbp < cfg['sbp_grade2']:
                evidence.append(f"Hypotension (SBP {sbp:.1f} mmHg < {cfg['sbp_grade2']} mmHg)")
            if si is not None and si > cfg['shock_index_grade2']:
                evidence.append(f"Uncompensated shock index (SI {si:.2f} > {cfg['shock_index_grade2']})")
            if hr is not None and hr >= cfg['hr_high_grade2']:
                evidence.append(f"Marked tachycardia (HR {hr:.1f} >= {cfg['hr_high_grade2']} bpm)")

        # Grade 1: Borderline perfusion / compensated shock
        elif (map_val is not None and map_val < cfg['map_grade1']) or \
             (sbp is not None and sbp < cfg['sbp_grade1']) or \
             (si is not None and si > cfg['shock_index_grade1']) or \
             (hr is not None and hr >= cfg['hr_high_grade1']):
            grade = 1
            if map_val is not None and map_val < cfg['map_grade1']:
                evidence.append(f"Borderline perfusion pressure (MAP {map_val:.1f} mmHg < {cfg['map_grade1']} mmHg)")
            if sbp is not None and sbp < cfg['sbp_grade1']:
                evidence.append(f"Borderline SBP ({sbp:.1f} mmHg < {cfg['sbp_grade1']} mmHg)")
            if si is not None and si > cfg['shock_index_grade1']:
                evidence.append(f"Compensated shock index (SI {si:.2f} > {cfg['shock_index_grade1']})")
            if hr is not None and hr >= cfg['hr_high_grade1']:
                evidence.append(f"Mild tachycardia (HR {hr:.1f} >= {cfg['hr_high_grade1']} bpm)")
        else:
            evidence.append("Hemodynamics stable; perfusion pressure within target clinical range.")

        descriptions = {
            0: "Normal Hemodynamics / Adequate Perfusion",
            1: "Borderline Perfusion / Compensated Shock",
            2: "Uncompensated Shock / Moderate Hypotension",
            3: "Severe Shock / Cardiovascular Collapse (Vasoactive Agent Dependency)"
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing
        )


class RenalDetector(BaseOrganDetector):
    """
    Evaluates acute kidney injury and nitrogenous waste accumulation.
    Guideline: KDIGO Clinical Practice Guideline for AKI (2012).
    """

    def __init__(self):
        super().__init__(name="Renal", guideline="KDIGO AKI Guideline 2012")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        cr = self._get_val(vitals, 'creatinine_max', 'creatinine_mean', 'creatinine')
        bun = self._get_val(vitals, 'bun_max', 'bun_mean', 'bun')
        urine_rate = self._get_val(vitals, 'urine_rate_ml_kg_h')
        urine_total = self._get_val(vitals, 'total_urine_6h')

        if cr is None:
            missing.append("creatinine")
        if bun is None:
            missing.append("bun")

        cfg = RENAL_CONFIG

        # Grade 3: KDIGO Stage 3 / Severe renal failure / Anuria
        if (cr is not None and cr >= cfg['cr_grade3']) or \
           (bun is not None and bun >= cfg['bun_grade3']) or \
           (urine_rate is not None and urine_rate <= cfg['urine_rate_grade3']):
            grade = 3
            if cr is not None and cr >= cfg['cr_grade3']:
                evidence.append(f"KDIGO Stage 3 AKI (Creatinine {cr:.2f} mg/dL >= {cfg['cr_grade3']} mg/dL)")
            if bun is not None and bun >= cfg['bun_grade3']:
                evidence.append(f"Severe uremic toxicity (BUN {bun:.1f} mg/dL >= {cfg['bun_grade3']} mg/dL)")
            if urine_rate is not None and urine_rate <= cfg['urine_rate_grade3']:
                evidence.append(f"Severe oliguria / anuria (Urine rate {urine_rate:.2f} ml/kg/h <= {cfg['urine_rate_grade3']})")

        # Grade 2: KDIGO Stage 2 / Moderate renal dysfunction / Oliguria
        elif (cr is not None and cr >= cfg['cr_grade2']) or \
             (bun is not None and bun >= cfg['bun_grade2']) or \
             (urine_rate is not None and urine_rate <= cfg['urine_rate_grade2']):
            grade = 2
            if cr is not None and cr >= cfg['cr_grade2']:
                evidence.append(f"KDIGO Stage 2 AKI (Creatinine {cr:.2f} mg/dL >= {cfg['cr_grade2']} mg/dL)")
            if bun is not None and bun >= cfg['bun_grade2']:
                evidence.append(f"Azotemia (BUN {bun:.1f} mg/dL >= {cfg['bun_grade2']} mg/dL)")
            if urine_rate is not None and urine_rate <= cfg['urine_rate_grade2']:
                evidence.append(f"Oliguria (Urine rate {urine_rate:.2f} ml/kg/h <= {cfg['urine_rate_grade2']})")

        # Grade 1: KDIGO Stage 1 / Early renal stress
        elif (cr is not None and cr >= cfg['cr_grade1']) or \
             (bun is not None and bun >= cfg['bun_grade1']) or \
             (urine_rate is not None and urine_rate <= cfg['urine_rate_grade1']):
            grade = 1
            if cr is not None and cr >= cfg['cr_grade1']:
                evidence.append(f"KDIGO Stage 1 AKI (Creatinine {cr:.2f} mg/dL >= {cfg['cr_grade1']} mg/dL)")
            if bun is not None and bun >= cfg['bun_grade1']:
                evidence.append(f"Mild azotemia (BUN {bun:.1f} mg/dL >= {cfg['bun_grade1']} mg/dL)")
            if urine_rate is not None and urine_rate <= cfg['urine_rate_grade1']:
                evidence.append(f"Low urine output (Urine rate {urine_rate:.2f} ml/kg/h <= {cfg['urine_rate_grade1']})")
        else:
            evidence.append("Renal clearance markers within acceptable baseline.")

        descriptions = {
            0: "Normal Renal Function",
            1: "KDIGO Stage 1 AKI / Mild Renal Impairment",
            2: "KDIGO Stage 2 AKI / Moderate Renal Failure",
            3: "KDIGO Stage 3 AKI / Severe Acute Kidney Injury (Dialysis Risk)"
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing
        )


class NeurologicalDetector(BaseOrganDetector):
    """
    Evaluates level of consciousness and airway protective reflex competency.
    Guideline: Glasgow Coma Scale (GCS) Clinical Triage.
    """

    def __init__(self):
        super().__init__(name="Neurological", guideline="Glasgow Coma Scale Triage")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        gcs = self._get_val(vitals, 'gcs_min', 'gcs_mean', 'gcs', 'gcstotal')

        if gcs is None:
            missing.append("gcs")
            evidence.append("GCS not documented in recent observation window.")
            return OrganAssessment(
                organ_name=self.name,
                grade=0,
                description="Neurological Status Not Documented (Presumed Baseline)",
                clinical_evidence=evidence,
                guideline_reference=self.guideline,
                missing_indicators=missing
            )

        cfg = NEUROLOGICAL_CONFIG

        # Grade 3: GCS <= 8 (Severe coma / loss of airway reflexes)
        if gcs <= cfg['gcs_grade3']:
            grade = 3
            evidence.append(f"Severe coma / depressed consciousness (GCS {gcs:.0f} <= {cfg['gcs_grade3']:.0f}); Airway compromised.")

        # Grade 2: GCS 9 - 12 (Moderate impairment / obtundation)
        elif gcs <= cfg['gcs_grade2']:
            grade = 2
            evidence.append(f"Moderate neurological impairment / stupor (GCS {gcs:.0f} <= {cfg['gcs_grade2']:.0f})")

        # Grade 1: GCS 13 - 14 (Mild confusion / encephalopathy)
        elif gcs <= cfg['gcs_grade1']:
            grade = 1
            evidence.append(f"Mild encephalopathy or sedation (GCS {gcs:.0f} <= {cfg['gcs_grade1']:.0f})")
        else:
            evidence.append(f"Fully conscious / intact airway reflexes (GCS {gcs:.0f})")

        descriptions = {
            0: "Alert / Fully Conscious (GCS 15)",
            1: "Mild Encephalopathy / Lethargy (GCS 13-14)",
            2: "Moderate Neurological Impairment / Stupor (GCS 9-12)",
            3: "Severe Coma / Loss of Airway Protection (GCS <= 8)"
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing
        )


class SepsisDetector(BaseOrganDetector):
    """
    Evaluates Systemic Inflammatory Response Syndrome (SIRS) and septic metabolic stress.
    Guideline: Surviving Sepsis Campaign (SSC 2021) & Consensus SIRS Criteria.
    """

    def __init__(self):
        super().__init__(name="Sepsis", guideline="SSC 2021 & ACCP/SCCM SIRS Criteria")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        temp = self._get_val(vitals, 'temperature_max', 'temperature_min', 'temperature_mean', 'temperature')
        hr = self._get_val(vitals, 'heartrate_max', 'heartrate_mean', 'heartrate')
        rr = self._get_val(vitals, 'resprate_max', 'respiration_rate', 'resprate_mean', 'resprate')
        wbc = self._get_val(vitals, 'wbc_max', 'wbc_mean', 'wbc')
        lactate = self._get_val(vitals, 'lactate_max', 'lactate_mean', 'lactate')

        cfg = SEPSIS_CONFIG

        # Count SIRS criteria fulfilled
        sirs_count = 0
        sirs_details = []

        if temp is not None:
            if temp > cfg['temp_high']:
                sirs_count += 1
                sirs_details.append(f"Fever ({temp:.1f} °C > {cfg['temp_high']} °C)")
            elif temp < cfg['temp_low']:
                sirs_count += 1
                sirs_details.append(f"Hypothermia ({temp:.1f} °C < {cfg['temp_low']} °C)")
        else:
            missing.append("temperature")

        if hr is not None:
            if hr > cfg['hr_sirs']:
                sirs_count += 1
                sirs_details.append(f"Tachycardia ({hr:.1f} bpm > {cfg['hr_sirs']} bpm)")
        else:
            missing.append("heartrate")

        if rr is not None:
            if rr > cfg['rr_sirs']:
                sirs_count += 1
                sirs_details.append(f"Tachypnea ({rr:.1f} /min > {cfg['rr_sirs']} /min)")
        else:
            missing.append("respiration_rate")

        if wbc is not None:
            if wbc > cfg['wbc_high']:
                sirs_count += 1
                sirs_details.append(f"Leukocytosis ({wbc:.1f} > {cfg['wbc_high']} x10^9/L)")
            elif wbc < cfg['wbc_low']:
                sirs_count += 1
                sirs_details.append(f"Leukopenia ({wbc:.1f} < {cfg['wbc_low']} x10^9/L)")
        else:
            missing.append("wbc")

        if lactate is None:
            missing.append("lactate")

        # Grading logic based on SIRS burden and tissue hypoperfusion (lactate)
        # Grade 3: Septic Shock threshold / Severe cellular dysoxia
        if (lactate is not None and lactate >= cfg['lactate_grade3']) or \
           (sirs_count >= 2 and lactate is not None and lactate >= cfg['lactate_grade2']):
            grade = 3
            evidence.append(f"Severe septic dysoxia (Lactate {lactate:.1f} mmol/L)")
            evidence.extend(sirs_details)

        # Grade 2: Sepsis with suspected organ hypoperfusion
        elif (sirs_count >= 2 and lactate is not None and lactate >= cfg['lactate_grade1']) or \
             (lactate is not None and lactate >= cfg['lactate_grade2']) or \
             (sirs_count >= 3):
            grade = 2
            if lactate is not None and lactate >= cfg['lactate_grade1']:
                evidence.append(f"Hyperlactatemia / hypoperfusion (Lactate {lactate:.1f} mmol/L >= {cfg['lactate_grade1']})")
            evidence.extend(sirs_details)

        # Grade 1: SIRS Positive (2+ criteria) without severe hyperlactatemia
        elif sirs_count >= 2 or (lactate is not None and lactate >= cfg['lactate_grade1']):
            grade = 1
            if sirs_count >= 2:
                evidence.append(f"SIRS criteria positive ({sirs_count}/4 criteria met)")
            if lactate is not None and lactate >= cfg['lactate_grade1']:
                evidence.append(f"Mild hyperlactatemia (Lactate {lactate:.1f} mmol/L)")
            evidence.extend(sirs_details)
        else:
            evidence.append("No active systemic inflammatory response syndrome (SIRS criteria < 2).")

        descriptions = {
            0: "No Systemic Inflammatory Response",
            1: "Systemic Inflammatory Response Syndrome (SIRS)",
            2: "Sepsis with Hypoperfusion Marker / High SIRS Burden",
            3: "Severe Septic Dysoxia / Impending Septic Shock"
        }

        actions = {
            0: "Routine clinical and infection surveillance.",
            1: "Draw blood cultures x2, check lactate, monitor temperature and vital signs q2h.",
            2: "Initiate Surviving Sepsis Hour-1 bundle: IV broad-spectrum antibiotics, 30 mL/kg crystalloids, serial lactate.",
            3: "Immediate septic resuscitation: central venous access, norepinephrine infusion target MAP >= 65, ICU consult."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )


class HepaticDetector(BaseOrganDetector):
    """
    Evaluates acute liver injury, cholestasis, and impaired hepatic protein synthesis.
    Guideline: SOFA Liver Component & Child-Pugh / EASL Critical Care Hepatology.
    """

    def __init__(self):
        super().__init__(name="Hepatic", guideline="SOFA Liver Component & Child-Pugh / EASL")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        bili = self._get_val(vitals, 'bilirubin_max', 'bilirubin_mean', 'bilirubin', 'total_bilirubin')
        inr = self._get_val(vitals, 'inr_max', 'inr_mean', 'inr')

        if bili is None:
            missing.append("bilirubin")
        if inr is None:
            missing.append("inr")

        cfg = HEPATIC_CONFIG

        # Grade 3: Severe hepatic failure / SOFA Liver Grade 3-4 / Fulminant coagulopathy
        if (bili is not None and bili >= cfg['bili_grade3']) or (inr is not None and inr >= cfg['inr_grade3']):
            grade = 3
            if bili is not None and bili >= cfg['bili_grade3']:
                evidence.append(f"Severe hyperbilirubinemia (Bilirubin {bili:.1f} mg/dL >= {cfg['bili_grade3']} mg/dL; SOFA Liver 3-4)")
            if inr is not None and inr >= cfg['inr_grade3']:
                evidence.append(f"Severe hepatic synthetic failure (INR {inr:.2f} >= {cfg['inr_grade3']})")

        # Grade 2: Moderate hepatic dysfunction / SOFA Liver Grade 2
        elif (bili is not None and bili >= cfg['bili_grade2']) or (inr is not None and inr >= cfg['inr_grade2']):
            grade = 2
            if bili is not None and bili >= cfg['bili_grade2']:
                evidence.append(f"Moderate hyperbilirubinemia (Bilirubin {bili:.1f} mg/dL >= {cfg['bili_grade2']} mg/dL; SOFA Liver 2)")
            if inr is not None and inr >= cfg['inr_grade2']:
                evidence.append(f"Impaired synthetic coagulopathy (INR {inr:.2f} >= {cfg['inr_grade2']})")

        # Grade 1: Mild liver stress / early jaundice / cholestasis
        elif (bili is not None and bili >= cfg['bili_grade1']) or (inr is not None and inr >= cfg['inr_grade1']):
            grade = 1
            if bili is not None and bili >= cfg['bili_grade1']:
                evidence.append(f"Mild hyperbilirubinemia (Bilirubin {bili:.1f} mg/dL >= {cfg['bili_grade1']} mg/dL)")
            if inr is not None and inr >= cfg['inr_grade1']:
                evidence.append(f"Mild INR elevation of hepatic origin (INR {inr:.2f} >= {cfg['inr_grade1']})")
        else:
            evidence.append("Hepatic synthetic clearance and bilirubin levels within acceptable physiological limits.")

        descriptions = {
            0: "Normal Hepatic Function",
            1: "Mild Hepatic Stress / Cholestasis",
            2: "Moderate Hepatic Dysfunction (SOFA Liver Grade 2)",
            3: "Severe Hepatic Failure / Decompensation (SOFA Liver Grade 3-4)"
        }

        actions = {
            0: "Routine clinical surveillance.",
            1: "Review hepatotoxic medications, monitor liver panel and coagulation daily.",
            2: "Dose adjust renally/hepatically cleared medications, perform liver ultrasound, screen for infection.",
            3: "Urgent hepatology consultation, evaluate for acute-on-chronic liver failure, start lactulose/rifaximin if encephalopathic, avoid sedatives."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )


class CoagulationDetector(BaseOrganDetector):
    """
    Evaluates platelet consumption, consumptive coagulopathy, and bleeding diathesis.
    Guideline: ISTH Overt DIC Scoring Guidelines & SOFA Coagulation Criteria.
    """

    def __init__(self):
        super().__init__(name="Coagulation", guideline="ISTH Overt DIC & SOFA Coagulation Criteria")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        plt = self._get_val(vitals, 'platelets_min', 'platelets_mean', 'platelets')
        inr = self._get_val(vitals, 'inr_max', 'inr_mean', 'inr')
        ptt = self._get_val(vitals, 'ptt_max', 'ptt_mean', 'ptt')

        if plt is None:
            missing.append("platelets")
        if inr is None:
            missing.append("inr")
        if ptt is None:
            missing.append("ptt")

        cfg = COAGULATION_CONFIG

        # Grade 3: Severe thrombocytopenia / critical coagulopathy / spontaneous bleeding risk
        if (plt is not None and plt < cfg['plt_grade3']) or \
           (inr is not None and inr >= cfg['inr_grade3']) or \
           (ptt is not None and ptt >= cfg['ptt_grade3']):
            grade = 3
            if plt is not None and plt < cfg['plt_grade3']:
                evidence.append(f"Severe thrombocytopenia (Platelets {plt:.0f} < {cfg['plt_grade3']} x10^9/L; SOFA Coag 3)")
            if inr is not None and inr >= cfg['inr_grade3']:
                evidence.append(f"Profound coagulopathy (INR {inr:.2f} >= {cfg['inr_grade3']})")
            if ptt is not None and ptt >= cfg['ptt_grade3']:
                evidence.append(f"Critical intrinsic pathway delay (PTT {ptt:.1f} s >= {cfg['ptt_grade3']} s)")

        # Grade 2: Moderate thrombocytopenia / coagulopathy / SOFA Grade 2
        elif (plt is not None and plt < cfg['plt_grade2']) or \
             (inr is not None and inr >= cfg['inr_grade2']) or \
             (ptt is not None and ptt >= cfg['ptt_grade2']):
            grade = 2
            if plt is not None and plt < cfg['plt_grade2']:
                evidence.append(f"Moderate thrombocytopenia (Platelets {plt:.0f} < {cfg['plt_grade2']} x10^9/L; SOFA Coag 2)")
            if inr is not None and inr >= cfg['inr_grade2']:
                evidence.append(f"Elevated coagulopathy risk (INR {inr:.2f} >= {cfg['inr_grade2']})")
            if ptt is not None and ptt >= cfg['ptt_grade2']:
                evidence.append(f"Prolonged PTT ({ptt:.1f} s >= {cfg['ptt_grade2']} s)")

        # Grade 1: Mild thrombocytopenia or mild prolongation
        elif (plt is not None and plt < cfg['plt_grade1']) or \
             (inr is not None and inr >= cfg['inr_grade1']) or \
             (ptt is not None and ptt >= cfg['ptt_grade1']):
            grade = 1
            if plt is not None and plt < cfg['plt_grade1']:
                evidence.append(f"Mild thrombocytopenia (Platelets {plt:.0f} < {cfg['plt_grade1']} x10^9/L)")
            if inr is not None and inr >= cfg['inr_grade1']:
                evidence.append(f"Borderline INR prolongation (INR {inr:.2f} >= {cfg['inr_grade1']})")
            if ptt is not None and ptt >= cfg['ptt_grade1']:
                evidence.append(f"Borderline PTT prolongation (PTT {ptt:.1f} s >= {cfg['ptt_grade1']} s)")
        else:
            evidence.append("Coagulation profile and platelet count within normal hemostatic parameters.")

        descriptions = {
            0: "Normal Hemostasis",
            1: "Mild Coagulation Stress / Mild Thrombocytopenia",
            2: "Moderate Coagulopathy / Consumptive Risk (SOFA Coag Grade 2)",
            3: "Severe Coagulopathy / Critical Bleeding Hazard (SOFA Coag Grade 3-4)"
        }

        actions = {
            0: "Routine clinical surveillance.",
            1: "Monitor serial CBC and coags q12h; avoid unnecessary intramuscular injections.",
            2: "Hold prophylactic anticoagulation if active bleeding; type and cross; check fibrinogen and D-dimer.",
            3: "Urgent hematology consult; prepare platelet transfusion / cryoprecipitate / FFP for invasive procedures or bleeding; initiate massive transfusion protocol if hemorrhagic."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )


class MetabolicDetector(BaseOrganDetector):
    """
    Evaluates systemic acid-base equilibrium, acidemia, and metabolic dysoxia.
    Guideline: Stewart Acid-Base Approach & ABG Critical Care Protocols.
    """

    def __init__(self):
        super().__init__(name="Metabolic", guideline="Stewart Acid-Base Approach & ABG Protocols")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        ph = self._get_val(vitals, 'ph_min', 'ph_mean', 'ph', 'ph_max')
        ph_max_val = self._get_val(vitals, 'ph_max')
        lactate = self._get_val(vitals, 'lactate_max', 'lactate_mean', 'lactate')

        if ph is None and ph_max_val is None:
            missing.append("ph")
        if lactate is None:
            missing.append("lactate")

        cfg = METABOLIC_CONFIG

        # Grade 3: Severe acidemia (pH < 7.15) or Critical Lactate (>= 6.0)
        if (ph is not None and ph < cfg['ph_low_grade3']) or (lactate is not None and lactate >= cfg['lactate_grade3']):
            grade = 3
            if ph is not None and ph < cfg['ph_low_grade3']:
                evidence.append(f"Severe life-threatening acidemia (pH {ph:.2f} < {cfg['ph_low_grade3']})")
            if lactate is not None and lactate >= cfg['lactate_grade3']:
                evidence.append(f"Severe metabolic dysoxia (Lactate {lactate:.1f} mmol/L >= {cfg['lactate_grade3']} mmol/L)")

        # Grade 2: Moderate acidemia (pH < 7.25) or Lactate >= 4.0 or Severe alkalemia
        elif (ph is not None and (ph < cfg['ph_low_grade2'] or ph > cfg['ph_high_grade2'])) or \
             (ph_max_val is not None and ph_max_val > cfg['ph_high_grade2']) or \
             (lactate is not None and lactate >= cfg['lactate_grade2']):
            grade = 2
            if ph is not None and ph < cfg['ph_low_grade2']:
                evidence.append(f"Moderate acidemia (pH {ph:.2f} < {cfg['ph_low_grade2']})")
            if (ph is not None and ph > cfg['ph_high_grade2']) or (ph_max_val is not None and ph_max_val > cfg['ph_high_grade2']):
                val = ph_max_val if ph_max_val is not None and ph_max_val > cfg['ph_high_grade2'] else ph
                evidence.append(f"Severe alkalemia (pH {val:.2f} > {cfg['ph_high_grade2']})")
            if lactate is not None and lactate >= cfg['lactate_grade2']:
                evidence.append(f"Hyperlactatemia / cellular hypoperfusion (Lactate {lactate:.1f} mmol/L >= {cfg['lactate_grade2']})")

        # Grade 1: Mild acid-base disruption
        elif (ph is not None and (ph < cfg['ph_low_grade1'] or ph > cfg['ph_high_grade1'])) or \
             (lactate is not None and lactate >= cfg['lactate_grade1']):
            grade = 1
            if ph is not None and ph < cfg['ph_low_grade1']:
                evidence.append(f"Mild acidemia (pH {ph:.2f} < {cfg['ph_low_grade1']})")
            if ph is not None and ph > cfg['ph_high_grade1']:
                evidence.append(f"Mild alkalemia (pH {ph:.2f} > {cfg['ph_high_grade1']})")
            if lactate is not None and lactate >= cfg['lactate_grade1']:
                evidence.append(f"Borderline lactate elevation (Lactate {lactate:.1f} mmol/L)")
        else:
            evidence.append("Arterial acid-base balance and serum lactate within acceptable physiological range.")

        descriptions = {
            0: "Normal Acid-Base Homeostasis",
            1: "Mild Acid-Base Imbalance / Borderline Hyperlactatemia",
            2: "Moderate Metabolic Acidemia / Tissue Hypoperfusion",
            3: "Severe Life-Threatening Acidemia / Metabolic Shutdown"
        }

        actions = {
            0: "Routine clinical observation.",
            1: "Serial blood gas evaluation in 4-6h; check hydration status and perfusion pressure.",
            2: "Identify underlying etiology (sepsis, renal, toxins); repeat lactate q2-4h; optimize microvascular perfusion.",
            3: "Immediate critical resuscitation: secure ventilation, titrate vasopressors, consider sodium bicarbonate if pH < 7.15 and refractory, evaluate urgent hemodialysis."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )


class EndocrineDetector(BaseOrganDetector):
    """
    Evaluates glycemic stability, acute neuroglycopenia risk, and hyperosmolar stress.
    Guideline: ADA Standards of Care for Hospitalized Patients & SSC Glycemic Guidelines.
    """

    def __init__(self):
        super().__init__(name="Endocrine", guideline="ADA Hospitalized Glycemic Protocols & SSC")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        glu_min = self._get_val(vitals, 'glucose_min')
        glu_max = self._get_val(vitals, 'glucose_max')
        glu_mean = self._get_val(vitals, 'glucose_mean', 'glucose')

        # Fallback if only one value exists
        effective_min = glu_min if glu_min is not None else glu_mean
        effective_max = glu_max if glu_max is not None else glu_mean

        if effective_min is None and effective_max is None:
            missing.append("glucose")

        cfg = ENDOCRINE_CONFIG

        # Grade 3: Severe hypoglycemia (<= 40) or Extreme Hyperglycemia (>= 400)
        if (effective_min is not None and effective_min <= cfg['glucose_hypo_grade3']) or \
           (effective_max is not None and effective_max >= cfg['glucose_hyper_grade3']):
            grade = 3
            if effective_min is not None and effective_min <= cfg['glucose_hypo_grade3']:
                evidence.append(f"Severe neuroglycopenia risk (Glucose {effective_min:.0f} mg/dL <= {cfg['glucose_hypo_grade3']:.0f} mg/dL)")
            if effective_max is not None and effective_max >= cfg['glucose_hyper_grade3']:
                evidence.append(f"Severe hyperosmolar hyperglycemia (Glucose {effective_max:.0f} mg/dL >= {cfg['glucose_hyper_grade3']:.0f} mg/dL)")

        # Grade 2: Significant hypoglycemia (<= 54) or DKA/HHS range (>= 250)
        elif (effective_min is not None and effective_min <= cfg['glucose_hypo_grade2']) or \
             (effective_max is not None and effective_max >= cfg['glucose_hyper_grade2']):
            grade = 2
            if effective_min is not None and effective_min <= cfg['glucose_hypo_grade2']:
                evidence.append(f"Clinically significant hypoglycemia (Glucose {effective_min:.0f} mg/dL <= {cfg['glucose_hypo_grade2']:.0f} mg/dL)")
            if effective_max is not None and effective_max >= cfg['glucose_hyper_grade2']:
                evidence.append(f"Marked hyperglycemia / DKA threshold (Glucose {effective_max:.0f} mg/dL >= {cfg['glucose_hyper_grade2']:.0f} mg/dL)")

        # Grade 1: Mild dysglycemia (<= 70 or >= 180)
        elif (effective_min is not None and effective_min <= cfg['glucose_hypo_grade1']) or \
             (effective_max is not None and effective_max >= cfg['glucose_hyper_grade1']):
            grade = 1
            if effective_min is not None and effective_min <= cfg['glucose_hypo_grade1']:
                evidence.append(f"Mild hypoglycemia alert (Glucose {effective_min:.0f} mg/dL <= {cfg['glucose_hypo_grade1']:.0f} mg/dL)")
            if effective_max is not None and effective_max >= cfg['glucose_hyper_grade1']:
                evidence.append(f"Stress hyperglycemia (Glucose {effective_max:.0f} mg/dL >= {cfg['glucose_hyper_grade1']:.0f} mg/dL)")
        else:
            evidence.append("Glycemic levels within critical care target envelope (70 - 180 mg/dL).")

        descriptions = {
            0: "Euglycemic / Target Controlled",
            1: "Mild Dysglycemia / Stress Hyperglycemia",
            2: "Significant Hypoglycemia or DKA/Hyperosmolar Range",
            3: "Critical Neuroglycopenia or Severe Hyperosmolar Crisis"
        }

        actions = {
            0: "Routine glucose surveillance (q4-6h).",
            1: "Titrate insulin regimen; target 140-180 mg/dL in ICU; recheck glucose in 2h.",
            2: "If hypoglycemic: administer 25g IV D50W stat, recheck in 15m. If hyperglycemic: check ketones, blood gas, start IV insulin infusion.",
            3: "Emergency bedside action: STAT IV D50W for hypoglycemia; aggressive IV fluid resuscitation + insulin infusion protocol for hyperosmolar state."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )


class HematologicDetector(BaseOrganDetector):
    """
    Evaluates acute anemia, oxygen carrying capacity, and transfusion requirements.
    Guideline: AABB Clinical Practice Guidelines & TRICC Restrictive Transfusion Protocols.
    """

    def __init__(self):
        super().__init__(name="Hematologic", guideline="AABB Transfusion Guidelines & TRICC Trial")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        hgb = self._get_val(vitals, 'hemoglobin_min', 'hemoglobin_mean', 'hemoglobin')

        if hgb is None:
            missing.append("hemoglobin")

        cfg = HEMATOLOGIC_CONFIG

        # Grade 3: Severe anemia (Hgb < 7.0 g/dL) - Restrictive transfusion trigger met
        if hgb is not None and hgb < cfg['hgb_grade3']:
            grade = 3
            evidence.append(f"Critical anemia below transfusion trigger (Hemoglobin {hgb:.1f} g/dL < {cfg['hgb_grade3']} g/dL)")

        # Grade 2: Moderate anemia (Hgb < 8.0 g/dL)
        elif hgb is not None and hgb < cfg['hgb_grade2']:
            grade = 2
            evidence.append(f"Moderate anemia (Hemoglobin {hgb:.1f} g/dL < {cfg['hgb_grade2']} g/dL; symptomatic threshold)")

        # Grade 1: Mild anemia (Hgb < 10.0 g/dL)
        elif hgb is not None and hgb < cfg['hgb_grade1']:
            grade = 1
            evidence.append(f"Mild anemia (Hemoglobin {hgb:.1f} g/dL < {cfg['hgb_grade1']} g/dL)")
        else:
            evidence.append("Hemoglobin and red cell oxygen carriage capacity preserved.")

        descriptions = {
            0: "Normal Hemoglobin / Oxygen Carrying Capacity",
            1: "Mild Anemia",
            2: "Moderate Anemia (Evaluation for Transfusion Threshold)",
            3: "Severe Critical Anemia (Restrictive Transfusion Trigger Reached)"
        }

        actions = {
            0: "Routine clinical monitoring.",
            1: "Track serial CBC daily; avoid excessive phlebotomy loss.",
            2: "Evaluate for acute blood loss, occult GI bleed, or hemolysis; crossmatch 2 units PRBCs on standby.",
            3: "Transfuse 1 unit PRBCs immediately, reassess post-transfusion hemoglobin; search for active source of hemorrhage."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )


class NutritionalDetector(BaseOrganDetector):
    """
    Evaluates nutritional vulnerability, severe cachexia, and metabolic reserve.
    Guideline: ASPEN / ESPEN Clinical Practice Guidelines for Nutrition Support in ICU.
    """

    def __init__(self):
        super().__init__(name="Nutritional", guideline="ASPEN/ESPEN Critical Care Nutrition Guidelines")

    def assess(self, vitals: Dict[str, Any]) -> OrganAssessment:
        evidence: List[str] = []
        missing: List[str] = []
        grade = 0

        bmi = self._get_val(vitals, 'bmi')
        weight = self._get_val(vitals, 'admissionweight')
        height = self._get_val(vitals, 'admissionheight')
        albumin = self._get_val(vitals, 'albumin_min', 'albumin_mean', 'albumin')

        # Fallback calculate BMI if missing but weight and height exist
        if bmi is None and weight is not None and height is not None and height > 0:
            # height in cm to m
            h_m = height / 100.0 if height > 3.0 else height
            if h_m > 0:
                bmi = weight / (h_m ** 2)

        if bmi is None:
            missing.append("bmi")
        if albumin is None:
            missing.append("albumin")

        cfg = NUTRITIONAL_CONFIG

        # Grade 3: Severe cachexia (BMI < 16) or critical hypoalbuminemia (< 2.2)
        if (bmi is not None and bmi < cfg['bmi_underweight_grade2']) or \
           (albumin is not None and albumin < cfg['albumin_grade2']):
            grade = 3
            if bmi is not None and bmi < cfg['bmi_underweight_grade2']:
                evidence.append(f"Severe wasting / cachexia (BMI {bmi:.1f} < {cfg['bmi_underweight_grade2']})")
            if albumin is not None and albumin < cfg['albumin_grade2']:
                evidence.append(f"Severe hypoalbuminemia / oncotic depletion (Albumin {albumin:.1f} g/dL < {cfg['albumin_grade2']} g/dL)")

        # Grade 2: Underweight (BMI < 18.5) or Class III Morbid Obesity (BMI >= 40) or Moderate hypoalbuminemia (< 3.0)
        elif (bmi is not None and (bmi < cfg['bmi_underweight_grade1'] or bmi >= cfg['bmi_obese_grade2'])) or \
             (albumin is not None and albumin < cfg['albumin_grade1']):
            grade = 2
            if bmi is not None and bmi < cfg['bmi_underweight_grade1']:
                evidence.append(f"Underweight status / malnutrition risk (BMI {bmi:.1f} < {cfg['bmi_underweight_grade1']})")
            if bmi is not None and bmi >= cfg['bmi_obese_grade2']:
                evidence.append(f"Class III morbid obesity (BMI {bmi:.1f} >= {cfg['bmi_obese_grade2']}; altered drug clearance)")
            if albumin is not None and albumin < cfg['albumin_grade1']:
                evidence.append(f"Hypoalbuminemia (Albumin {albumin:.1f} g/dL < {cfg['albumin_grade1']} g/dL)")

        # Grade 1: Class II Obesity (BMI >= 35) or borderline underweight
        elif bmi is not None and (bmi >= cfg['bmi_obese_grade1'] or bmi < 20.0):
            grade = 1
            if bmi >= cfg['bmi_obese_grade1']:
                evidence.append(f"Class II obesity (BMI {bmi:.1f} >= {cfg['bmi_obese_grade1']})")
            else:
                evidence.append(f"Borderline low BMI ({bmi:.1f} < 20.0)")
        else:
            evidence.append("Nutritional baseline and metabolic somatic reserve acceptable.")

        descriptions = {
            0: "Adequate Nutritional Reserve",
            1: "Mild Nutritional Vulnerability / Class II Obesity",
            2: "Malnutrition Risk / Class III Morbid Obesity / Hypoalbuminemia",
            3: "Severe Cachexia / Critical Refeeding Hazard"
        }

        actions = {
            0: "Standard ICU nutritional support within 24-48h.",
            1: "Dietitian evaluation; adjust medication dosing to ideal body weight.",
            2: "Early enteral nutrition protocol; monitor electrolytes (phosphate, potassium, magnesium) to prevent refeeding syndrome.",
            3: "Urgent nutrition consultation; initiate refeeding syndrome protocol with thiamine/electrolyte repletion before advancing calories."
        }

        return OrganAssessment(
            organ_name=self.name,
            grade=grade,
            description=descriptions[grade],
            clinical_evidence=evidence,
            guideline_reference=self.guideline,
            missing_indicators=missing,
            suggested_action=actions[grade]
        )

