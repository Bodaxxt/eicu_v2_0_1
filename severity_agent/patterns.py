"""
ICU Guard v4.2 — Clinical Syndrome & Pattern Detectors
======================================================
Identifies 5 complex multi-system critical care syndromes:
1. Septic Shock Pattern        (SSC 2021: Sepsis + Hypotension + Dysoxia)
2. ARDS Pattern                (Berlin Definition: Non-cardiogenic hypoxemia)
3. AKI Pattern                 (KDIGO: Sepsis-induced or ischemic nephropathy)
4. MOF Pattern                 (Multiple Organ Failure: >= 3 organ systems >= Grade 2)
5. Neuro-Respiratory Pattern   (Depressed consciousness + Loss of airway protection / aspiration risk)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging

from severity_agent.detectors import OrganAssessment
from severity_agent.config import PATTERN_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class PatternMatch:
    """Clinical diagnostic pattern result."""
    pattern_name: str
    detected: bool
    confidence: str               # "HIGH", "MODERATE", "LOW", "NONE"
    diagnostic_criteria_met: List[str] = field(default_factory=list)
    clinical_recommendation: str = ""
    urgency_tier: str = "ROUTINE" # "IMMEDIATE", "URGENT", "MONITOR", "ROUTINE"


class BasePattern(ABC):
    """Abstract base class for multi-system clinical syndrome patterns."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        """
        Evaluate if the syndrome pattern is manifested across organ systems.
        
        Args:
            organ_assessments: Dict mapping organ name to OrganAssessment.
            vitals: Raw patient vital signs and lab measurements.
        """
        pass


class SepticShockPattern(BasePattern):
    """
    Septic Shock Syndrome:
    Requires systemic inflammation / sepsis evidence + hemodynamic instability + cellular dysoxia (Lactate > 4.0).
    """

    def __init__(self):
        super().__init__(name="Septic Shock")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        sepsis = organ_assessments.get("Sepsis")
        hemo = organ_assessments.get("Hemodynamic")

        lactate = vitals.get('lactate_max') or vitals.get('lactate_mean') or vitals.get('lactate')
        try:
            lactate = float(lactate) if lactate is not None else None
        except (ValueError, TypeError):
            lactate = None

        has_sepsis = sepsis is not None and sepsis.grade >= 1
        has_hypotension = hemo is not None and hemo.grade >= 1
        has_dysoxia = lactate is not None and lactate >= PATTERN_CONFIG['septic_shock']['lactate_cutoff']

        if has_sepsis:
            criteria.append(f"Systemic infection/SIRS identified ({sepsis.description})")
        if has_hypotension:
            criteria.append(f"Vasomotor instability / hypotension identified ({hemo.description})")
        if has_dysoxia:
            criteria.append(f"Cellular hypoperfusion (Lactate {lactate:.1f} mmol/L >= {PATTERN_CONFIG['septic_shock']['lactate_cutoff']} mmol/L)")

        # Full septic shock: Sepsis + Hypotension + Lactate > 4
        if has_sepsis and has_hypotension and has_dysoxia:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Immediate Surviving Sepsis Hour-1 Bundle: 30 mL/kg crystalloids, blood cultures, broad-spectrum IV antibiotics, start norepinephrine titration to target MAP >= 65.",
                urgency_tier="IMMEDIATE"
            )
        # Probable / impending septic shock
        elif has_sepsis and (has_hypotension or has_dysoxia):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="High risk of septic decompensation: Fluid challenge response assessment, serial lactate clearance every 2-4h, early vasopressor line preparation.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Continue routine sepsis surveillance.",
            urgency_tier="ROUTINE"
        )


class ARDSPattern(BasePattern):
    """
    Acute Respiratory Distress Syndrome (Berlin Definition):
    Severe refractory hypoxemic respiratory failure with pulmonary consolidation / gas exchange barrier.
    """

    def __init__(self):
        super().__init__(name="Acute Respiratory Distress Syndrome (ARDS)")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        resp = organ_assessments.get("Respiratory")

        pao2 = vitals.get('pao2_min') or vitals.get('pao2_mean') or vitals.get('pao2')
        sao2 = vitals.get('sao2_min') or vitals.get('sao2_mean') or vitals.get('sao2')
        try:
            pao2 = float(pao2) if pao2 is not None else None
            sao2 = float(sao2) if sao2 is not None else None
        except (ValueError, TypeError):
            pass

        has_resp_injury = resp is not None and resp.grade >= 2
        has_severe_hypoxemia = (pao2 is not None and pao2 < 65.0) or (sao2 is not None and sao2 < 88.0)

        if has_resp_injury:
            criteria.append(f"Significant lung injury ({resp.description})")
        if has_severe_hypoxemia:
            val_str = f"PaO2 {pao2:.1f} mmHg" if pao2 is not None else f"SaO2 {sao2:.1f}%"
            criteria.append(f"Severe refractory hypoxemia ({val_str})")

        if has_resp_injury and has_severe_hypoxemia:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Implement lung-protective mechanical ventilation (tidal volume 4-6 mL/kg PBW, plateau pressure < 30 cmH2O), optimize PEEP titration, consider neuromuscular blockade or prone positioning if P/F < 150.",
                urgency_tier="IMMEDIATE"
            )
        elif has_resp_injury or (resp is not None and resp.grade == 1 and has_severe_hypoxemia):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Evaluate for early ARDS: high-flow nasal cannula (HFNC) with close ROX index monitoring; obtain immediate portable chest radiograph.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Maintain standard oxygenation targets (SpO2 92-96%).",
            urgency_tier="ROUTINE"
        )


class AKIPattern(BasePattern):
    """
    Acute Kidney Injury Syndrome:
    Renal dysfunction secondary to septic injury (endothelial / microvascular) or ischemic hypoperfusion.
    """

    def __init__(self):
        super().__init__(name="Acute Kidney Injury (Sepsis/Ischemia Induced)")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        renal = organ_assessments.get("Renal")
        sepsis = organ_assessments.get("Sepsis")
        hemo = organ_assessments.get("Hemodynamic")

        has_renal = renal is not None and renal.grade >= 1
        has_sepsis = sepsis is not None and sepsis.grade >= 1
        has_hemo = hemo is not None and hemo.grade >= 1

        if has_renal:
            criteria.append(f"Renal clearance compromise ({renal.description})")
        if has_sepsis:
            criteria.append(f"Concurrent sepsis trigger ({sepsis.description})")
        if has_hemo:
            criteria.append(f"Concurrent renal hypoperfusion trigger ({hemo.description})")

        # AKI with identified hemodynamic or septic driver, or intrinsic severe AKI (grade >= 2)
        if renal is not None and renal.grade >= 2:
            conf = "HIGH" if (has_sepsis or has_hemo or renal.grade >= 3) else "MODERATE"
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence=conf,
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Stop all nephrotoxic medications, optimize renal perfusion pressure (target MAP >= 65-70), maintain strict hourly Foley urine output monitoring, urgent nephrology consult for potential RRT.",
                urgency_tier="URGENT"
            )
        elif has_renal and (has_sepsis or has_hemo):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Early renal protection: Avoid contrast exposure, check serum electrolytes (potassium/acidosis surveillance), ensure adequate volume resuscitation.",
                urgency_tier="MONITOR"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Routine renal surveillance.",
            urgency_tier="ROUTINE"
        )


class MOFPattern(BasePattern):
    """
    Multiple Organ Failure (MOF / MODS):
    Simultaneous dysfunction in >= 3 organ systems with injury grade >= 2.
    """

    def __init__(self):
        super().__init__(name="Multiple Organ Failure (MOF/MODS)")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        failing_organs = []

        for name, assessment in organ_assessments.items():
            if assessment.grade >= 2:
                failing_organs.append(name)
                criteria.append(f"{name}: Grade {assessment.grade} failure ({assessment.description})")

        # >= 3 failing organs -> Critical MOF
        if len(failing_organs) >= 3:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation=f"Critical Multi-Organ Failure ({len(failing_organs)} organs involved: {', '.join(failing_organs)}). Immediate intensivist bedside conference, invasive hemodynamic monitoring, advanced life support bundle.",
                urgency_tier="IMMEDIATE"
            )
        elif len(failing_organs) == 2:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation=f"Bi-organ dysfunction detected ({', '.join(failing_organs)}). Aggressive intervention required to prevent progression into tertiary organ collapse.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No multi-organ failure detected.",
            urgency_tier="ROUTINE"
        )


class NeuroRespiratoryPattern(BasePattern):
    """
    Neuro-Respiratory Syndrome:
    Depressed consciousness (GCS <= 12) coupled with pulmonary insufficiency -> Extreme aspiration risk.
    """

    def __init__(self):
        super().__init__(name="Neuro-Respiratory Syndrome & Aspiration Risk")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        neuro = organ_assessments.get("Neurological")
        resp = organ_assessments.get("Respiratory")

        has_neuro = neuro is not None and neuro.grade >= 2
        has_resp = resp is not None and resp.grade >= 1

        if has_neuro:
            criteria.append(f"Depressed central airway control ({neuro.description})")
        if has_resp:
            criteria.append(f"Active pulmonary compromise ({resp.description})")

        if neuro is not None and neuro.grade == 3:  # GCS <= 8
            criteria.append("Absolute loss of gag/cough airway protection reflex (GCS <= 8)")
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Immediate airway protection: Endotracheal intubation indicated to secure airway and prevent catastrophic aspiration pneumonitis.",
                urgency_tier="IMMEDIATE"
            )
        elif has_neuro and has_resp:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Elevate head of bed to 30-45 degrees, place NGT on decompression, airway equipment at bedside on standby, frequent GCS re-evaluation.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Airway protective reflexes preserved.",
            urgency_tier="ROUTINE"
        )


class CardiogenicShockPattern(BasePattern):
    """
    Cardiogenic Shock Syndrome:
    Pump failure characterized by systemic hypoperfusion (MAP < 65), narrow pulse pressure (<= 30 mmHg),
    and hydrostatic pulmonary congestion.
    """

    def __init__(self):
        super().__init__(name="Cardiogenic Shock")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        hemo = organ_assessments.get("Hemodynamic")
        resp = organ_assessments.get("Respiratory")

        sbp = vitals.get('sbp_min') or vitals.get('sbp_mean') or vitals.get('sbp')
        dbp = vitals.get('dbp_min') or vitals.get('dbp_mean') or vitals.get('dbp')
        pulse_press = vitals.get('pulse_pressure')
        si = vitals.get('shock_index_max') or vitals.get('shock_index')

        def to_f(val):
            try:
                return float(val) if val is not None else None
            except:
                return None

        sbp = to_f(sbp)
        dbp = to_f(dbp)
        pulse_press = to_f(pulse_press)
        si = to_f(si)

        if pulse_press is None and sbp is not None and dbp is not None:
            pulse_press = sbp - dbp

        cfg = PATTERN_CONFIG['cardiogenic_shock']
        has_hypotension = hemo is not None and hemo.grade >= 1
        has_narrow_pp = pulse_press is not None and pulse_press <= cfg['pulse_pressure_cutoff']
        has_elevated_si = si is not None and si >= cfg['shock_index_cutoff']
        has_pulmonary_congestion = resp is not None and resp.grade >= cfg['min_resp_grade']

        if has_hypotension:
            criteria.append(f"Systemic hypoperfusion present ({hemo.description})")
        if has_narrow_pp:
            criteria.append(f"Narrow pulse pressure ({pulse_press:.1f} mmHg <= {cfg['pulse_pressure_cutoff']} mmHg; stroke volume depletion)")
        if has_elevated_si:
            criteria.append(f"Elevated shock index ({si:.2f} >= {cfg['shock_index_cutoff']})")
        if has_pulmonary_congestion:
            criteria.append(f"Concurrent pulmonary congestion/dysfunction ({resp.description})")

        # Full pattern: Hypotension + Narrow Pulse Pressure + Pulmonary Involvement
        if has_hypotension and has_narrow_pp and has_pulmonary_congestion:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Urgent bedside echocardiography / POCUS; initiate inotropic support (dobutamine/milrinone); avoid excessive fluid boluses; consider cardiology consult for mechanical circulatory support (IABP/Impella).",
                urgency_tier="IMMEDIATE"
            )
        elif (has_hypotension or has_elevated_si) and (has_narrow_pp or has_pulmonary_congestion):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Suspected cardiogenic hypoperfusion: Perform focused cardiac ultrasound, track troponin and BNP, cautious fluid challenge only under dynamic monitoring.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No overt cardiogenic shock profile.",
            urgency_tier="ROUTINE"
        )


class HemorrhagicShockPattern(BasePattern):
    """
    Hemorrhagic / Hypovolemic Shock:
    Acute blood loss characterized by severe anemia, acute tachycardia, and vasomotor collapse.
    """

    def __init__(self):
        super().__init__(name="Hemorrhagic / Hypovolemic Shock")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        hemo = organ_assessments.get("Hemodynamic")
        hemat = organ_assessments.get("Hematologic")

        hgb = vitals.get('hemoglobin_min') or vitals.get('hemoglobin_mean') or vitals.get('hemoglobin')
        hr = vitals.get('heartrate_max') or vitals.get('heartrate_mean') or vitals.get('heartrate')
        map_val = vitals.get('meanbp_min') or vitals.get('meanbp_mean') or vitals.get('meanbp')
        si = vitals.get('shock_index_max') or vitals.get('shock_index')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        hgb = to_f(hgb)
        hr = to_f(hr)
        map_val = to_f(map_val)
        si = to_f(si)

        cfg = PATTERN_CONFIG['hemorrhagic_shock']
        is_anemic = (hgb is not None and hgb < cfg['hgb_cutoff']) or (hemat is not None and hemat.grade >= 2)
        is_hypotensive = (map_val is not None and map_val < cfg['map_cutoff']) or (hemo is not None and hemo.grade >= 1)
        is_tachycardic = (hr is not None and hr >= cfg['hr_cutoff']) or (si is not None and si >= cfg['shock_index_cutoff'])

        if is_anemic:
            criteria.append(f"Significant anemia / blood loss marker (Hgb {hgb if hgb is not None else 'N/A'} < {cfg['hgb_cutoff']} g/dL)")
        if is_hypotensive:
            criteria.append(f"Perfusion failure / hypotension (MAP {map_val if map_val is not None else 'N/A'} < {cfg['map_cutoff']} mmHg)")
        if is_tachycardic:
            criteria.append(f"Compensatory tachycardia / high shock index (HR {hr if hr is not None else 'N/A'} >= {cfg['hr_cutoff']} bpm)")

        if is_anemic and is_hypotensive and is_tachycardic:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Activate Massive Transfusion Protocol (1:1:1 PRBC:FFP:Platelets); administer Tranexamic Acid (TXA 1g IV); urgent surgical/endoscopic source control; warm fluids to prevent lethal triad.",
                urgency_tier="IMMEDIATE"
            )
        elif is_anemic and (is_hypotensive or is_tachycardic):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="High risk of occult hemorrhage: Type and crossmatch 2 units PRBCs, serial Hgb every 2-4h, search for gastrointestinal, retroperitoneal, or surgical bleeding site.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No overt hemorrhagic shock pattern.",
            urgency_tier="ROUTINE"
        )


class DICPattern(BasePattern):
    """
    Disseminated Intravascular Coagulation (DIC):
    Consumptive coagulopathy with microvascular thrombosis and bleeding risk (ISTH criteria).
    """

    def __init__(self):
        super().__init__(name="Disseminated Intravascular Coagulation (DIC)")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        coag = organ_assessments.get("Coagulation")
        sepsis = organ_assessments.get("Sepsis")

        plt = vitals.get('platelets_min') or vitals.get('platelets_mean') or vitals.get('platelets')
        inr = vitals.get('inr_max') or vitals.get('inr_mean') or vitals.get('inr')
        ptt = vitals.get('ptt_max') or vitals.get('ptt_mean') or vitals.get('ptt')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        plt = to_f(plt)
        inr = to_f(inr)
        ptt = to_f(ptt)

        cfg = PATTERN_CONFIG['dic']
        has_thrombocytopenia = (plt is not None and plt < cfg['plt_cutoff']) or (coag is not None and coag.grade >= 2)
        has_prolonged_coags = (inr is not None and inr >= cfg['inr_cutoff']) or (ptt is not None and ptt >= cfg['ptt_cutoff'])
        has_trigger = (sepsis is not None and sepsis.grade >= 1) or any(a.grade >= 2 for a in organ_assessments.values())

        if has_thrombocytopenia:
            criteria.append(f"Platelet consumption (Platelets {plt if plt is not None else 'N/A'} < {cfg['plt_cutoff']} x10^9/L)")
        if has_prolonged_coags:
            criteria.append(f"Clotting factor consumption (INR {inr if inr is not None else 'N/A'}, PTT {ptt if ptt is not None else 'N/A'} s)")
        if has_trigger:
            criteria.append("Underlying pro-inflammatory / tissue factor trigger present (Sepsis / MOF)")

        if has_thrombocytopenia and has_prolonged_coags and has_trigger:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Treat underlying etiology aggressively; check fibrinogen, D-dimer, peripheral smear; transfuse cryoprecipitate if fibrinogen < 150 mg/dL, platelets if < 50k with active bleeding.",
                urgency_tier="IMMEDIATE"
            )
        elif has_thrombocytopenia and has_prolonged_coags:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Consumptive coagulopathy suspected: Serial coagulation panels, monitor for microvascular bleeding or thrombosis, avoid unnecessary invasive instrumentation.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No overt DIC pattern detected.",
            urgency_tier="ROUTINE"
        )


class DeliriumPattern(BasePattern):
    """
    Delirium & Acute Brain Dysfunction:
    Fluctuating altered mental status, encephalopathy, or acute subcoma cognitive decline.
    """

    def __init__(self):
        super().__init__(name="Delirium & Acute Brain Dysfunction")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        neuro = organ_assessments.get("Neurological")
        gcs = vitals.get('gcs_min') or vitals.get('gcs_mean') or vitals.get('gcs')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        gcs = to_f(gcs)
        cfg = PATTERN_CONFIG['delirium']

        # Delirium is characterized by mild-to-moderate encephalopathy (GCS 9-14) rather than deep unarousable coma (GCS <= 8)
        is_altered = (gcs is not None and cfg['gcs_min'] <= gcs <= cfg['gcs_max']) or \
                     (neuro is not None and neuro.grade in [1, 2])

        if is_altered:
            criteria.append(f"Altered mental status / sub-coma cognitive fluctuation (GCS {gcs if gcs is not None else 'documented'})")

        if is_altered:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Initiate ICU Delirium Bundle (ABCDEF): CAM-ICU screening, reorientation, optimize sleep-wake cycle, avoid benzodiazepines/anticholinergics, early mobility, assess for underlying pain or infection.",
                urgency_tier="MONITOR"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Neurological status consistent with baseline or deep sedation.",
            urgency_tier="ROUTINE"
        )


class RefractoryShockPattern(BasePattern):
    """
    Refractory Vasodilatory / Septic Shock:
    Persistent hypotension requiring escalating vasopressor support with elevated cellular dysoxia.
    """

    def __init__(self):
        super().__init__(name="Refractory Vasodilatory Shock")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        hemo = organ_assessments.get("Hemodynamic")

        vaso = vitals.get('vasopressor_6h')
        map_val = vitals.get('meanbp_min') or vitals.get('meanbp_mean') or vitals.get('meanbp')
        lactate = vitals.get('lactate_max') or vitals.get('lactate_mean') or vitals.get('lactate')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        vaso = to_f(vaso)
        map_val = to_f(map_val)
        lactate = to_f(lactate)

        cfg = PATTERN_CONFIG['refractory_shock']
        on_vasopressors = vaso is not None and vaso >= 1.0
        has_hypotension = (map_val is not None and map_val < cfg['map_cutoff']) or (hemo is not None and hemo.grade >= 2)
        has_dysoxia = lactate is not None and lactate >= cfg['lactate_cutoff']

        if on_vasopressors:
            criteria.append("Active continuous vasopressor infusion in progress")
        if has_hypotension:
            criteria.append(f"Persistent failure to maintain target MAP (MAP {map_val if map_val is not None else 'N/A'} < {cfg['map_cutoff']} mmHg)")
        if has_dysoxia:
            criteria.append(f"Ongoing cellular dysoxia (Lactate {lactate:.1f} mmol/L >= {cfg['lactate_cutoff']} mmol/L)")

        if on_vasopressors and (has_hypotension or has_dysoxia):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Start second-line vasopressor (Vasopressin 0.03 units/min non-titrated); start stress-dose IV hydrocortisone (200 mg/day); perform bedside echocardiogram to evaluate RV strain and cardiac output; consider Angiotensin II.",
                urgency_tier="IMMEDIATE"
            )
        elif has_hypotension and has_dysoxia:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Unresponsive shock state: Ensure adequate intravascular volume repletion, titrate norepinephrine infusion, place arterial line for continuous arterial blood pressure monitoring.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No evidence of refractory shock state.",
            urgency_tier="ROUTINE"
        )


class Type1RespiratoryFailurePattern(BasePattern):
    """
    Type 1 (Hypoxemic) Respiratory Failure:
    Failure of oxygenation without carbon dioxide retention (PaO2 < 60 mmHg or SaO2 < 90% with PaCO2 <= 45 mmHg).
    """

    def __init__(self):
        super().__init__(name="Type 1 (Hypoxemic) Respiratory Failure")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        resp = organ_assessments.get("Respiratory")

        pao2 = vitals.get('pao2_min') or vitals.get('pao2_mean') or vitals.get('pao2')
        sao2 = vitals.get('sao2_min') or vitals.get('sao2_mean') or vitals.get('sao2')
        paco2 = vitals.get('paco2_max') or vitals.get('paco2_mean') or vitals.get('paco2')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        pao2 = to_f(pao2)
        sao2 = to_f(sao2)
        paco2 = to_f(paco2)

        cfg = PATTERN_CONFIG['type1_resp_failure']
        is_hypoxemic = (pao2 is not None and pao2 < cfg['pao2_cutoff']) or \
                       (sao2 is not None and sao2 < cfg['sao2_cutoff']) or \
                       (resp is not None and resp.grade >= 2)
        is_normo_or_hypocapnic = paco2 is None or paco2 <= cfg['paco2_max']

        if is_hypoxemic:
            criteria.append(f"Severe hypoxemic gas exchange failure (PaO2 {pao2 if pao2 else 'N/A'}, SaO2 {sao2 if sao2 else 'N/A'}%)")
        if is_normo_or_hypocapnic and paco2 is not None:
            criteria.append(f"Non-hypercapnic alveolar ventilation (PaCO2 {paco2:.1f} mmHg <= {cfg['paco2_max']} mmHg)")

        if is_hypoxemic and is_normo_or_hypocapnic:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH" if pao2 is not None else "MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Escalate oxygen therapy: High-Flow Nasal Cannula (HFNC) or trial of CPAP; investigate V/Q mismatch causes (pneumonia, pulmonary embolism, atelectasis); prepare for lung-protective mechanical ventilation if deteriorating.",
                urgency_tier="IMMEDIATE"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Oxygenation within acceptable clinical thresholds.",
            urgency_tier="ROUTINE"
        )


class Type2RespiratoryFailurePattern(BasePattern):
    """
    Type 2 (Hypercapnic / Ventilatory Pump) Respiratory Failure:
    Failure of ventilation characterized by CO2 retention (PaCO2 > 50 mmHg) and acute respiratory acidemia.
    """

    def __init__(self):
        super().__init__(name="Type 2 (Hypercapnic) Respiratory Failure")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []

        paco2 = vitals.get('paco2_max') or vitals.get('paco2_mean') or vitals.get('paco2')
        ph = vitals.get('ph_min') or vitals.get('ph_mean') or vitals.get('ph')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        paco2 = to_f(paco2)
        ph = to_f(ph)

        cfg = PATTERN_CONFIG['type2_resp_failure']
        has_hypercapnia = paco2 is not None and paco2 >= cfg['paco2_cutoff']
        has_acidemia = ph is not None and ph < cfg['ph_cutoff']

        if has_hypercapnia:
            criteria.append(f"Alveolar hypoventilation / CO2 retention (PaCO2 {paco2:.1f} mmHg >= {cfg['paco2_cutoff']} mmHg)")
        if has_acidemia:
            criteria.append(f"Acute respiratory acidemia (pH {ph:.2f} < {cfg['ph_cutoff']})")

        if has_hypercapnia and has_acidemia:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Immediate non-invasive ventilation (BiPAP/NIV) trial if cooperative; assess for airway obstruction, COPD exacerbation, or central hypoventilation; prepare for urgent endotracheal intubation if sensorium declines.",
                urgency_tier="IMMEDIATE"
            )
        elif has_hypercapnia:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Chronic or compensated hypercapnia: Serial ABG monitoring, evaluate bronchodilator response, avoid excessive unmonitored oxygen that blunts respiratory drive.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No evidence of hypercapnic ventilatory pump failure.",
            urgency_tier="ROUTINE"
        )


class HepatorenalSyndromePattern(BasePattern):
    """
    Hepatorenal Syndrome (HRS-AKI):
    Acute kidney injury occurring in the setting of severe hepatic dysfunction.
    """

    def __init__(self):
        super().__init__(name="Hepatorenal Syndrome (HRS-AKI)")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        hep = organ_assessments.get("Hepatic")
        renal = organ_assessments.get("Renal")
        hemo = organ_assessments.get("Hemodynamic")

        has_liver_injury = hep is not None and hep.grade >= 2
        has_renal_injury = renal is not None and renal.grade >= 2

        if has_liver_injury:
            criteria.append(f"Moderate-to-severe hepatic failure present ({hep.description})")
        if has_renal_injury:
            criteria.append(f"Acute kidney injury present ({renal.description})")

        if has_liver_injury and has_renal_injury:
            confidence = "HIGH" if (hemo is None or hemo.grade < 3) else "MODERATE"
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence=confidence,
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Manage as HRS-AKI: Discontinue all diuretics and nephrotoxic drugs; initiate IV Albumin volume expansion (1 g/kg, max 100g/day); start Terlipressin or Norepinephrine infusion; nephrology and transplant hepatology consult.",
                urgency_tier="IMMEDIATE"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No combined hepatorenal failure syndrome detected.",
            urgency_tier="ROUTINE"
        )


class PostoperativeDeteriorationPattern(BasePattern):
    """
    Post-Operative Acute Deterioration:
    Acute physiological decompensation in a patient newly admitted from OR, PACU, or Recovery Room.
    """

    def __init__(self):
        super().__init__(name="Post-Operative Deterioration")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []

        # Check surgical admission flags in features
        adm_pacu = vitals.get('admissiontype_PACU', 0)
        adm_or = vitals.get('admissiontype_Operating Room', 0)
        adm_rec = vitals.get('admissiontype_Recovery Room', 0)
        unit_sicu = vitals.get('unittype_SICU', 0)
        unit_csicu = vitals.get('unittype_CSICU', 0)

        is_surgical = bool(adm_pacu or adm_or or adm_rec or unit_sicu or unit_csicu)

        hemo = organ_assessments.get("Hemodynamic")
        resp = organ_assessments.get("Respiratory")
        hemat = organ_assessments.get("Hematologic")

        has_instability = any(
            a is not None and a.grade >= 1
            for a in [hemo, resp, hemat]
        )

        if is_surgical:
            criteria.append("Post-surgical admission pathway (OR / PACU / SICU / Recovery)")
        if has_instability:
            criteria.append("Acute postoperative physiological instability detected")

        if is_surgical and has_instability:
            max_g = max((a.grade for a in [hemo, resp, hemat] if a is not None), default=0)
            conf = "HIGH" if max_g >= 2 else "MODERATE"
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence=conf,
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Urgent surgical bedside re-evaluation: Rule out occult postoperative hemorrhage, check surgical site/drains, ensure reversal of residual neuromuscular blockade, obtain portable chest radiograph.",
                urgency_tier="URGENT" if max_g >= 2 else "MONITOR"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No acute post-operative deterioration detected.",
            urgency_tier="ROUTINE"
        )


class SevereAcidemiaPattern(BasePattern):
    """
    Severe Acidemia & Metabolic Crisis:
    Critical systemic acidemia (pH < 7.20) leading to myocardial depression and vascular paresis.
    """

    def __init__(self):
        super().__init__(name="Severe Acidemia & Metabolic Crisis")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        ph = vitals.get('ph_min') or vitals.get('ph_mean') or vitals.get('ph')
        lactate = vitals.get('lactate_max') or vitals.get('lactate_mean') or vitals.get('lactate')
        metab = organ_assessments.get("Metabolic")

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        ph = to_f(ph)
        lactate = to_f(lactate)

        cfg = PATTERN_CONFIG['severe_acidemia']
        is_severe_ph = ph is not None and ph < cfg['ph_cutoff']
        is_metab_grade3 = metab is not None and metab.grade == 3

        if is_severe_ph:
            criteria.append(f"Critical acidemia (pH {ph:.2f} < {cfg['ph_cutoff']}; myocardial depression risk)")
        if lactate is not None and lactate >= 4.0:
            criteria.append(f"Concurrent lactic acidosis component (Lactate {lactate:.1f} mmol/L)")

        if is_severe_ph or is_metab_grade3:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Critical metabolic stabilization: Maintain alveolar ventilation to blow off CO2, correct severe hypoperfusion, evaluate emergent continuous veno-venous hemodiafiltration (CVVHDF), consider IV buffer therapy if pH < 7.15 and refractory.",
                urgency_tier="IMMEDIATE"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="Acid-base status above severe acidemia critical cutoff.",
            urgency_tier="ROUTINE"
        )


class HyperosmolarCrisisPattern(BasePattern):
    """
    Hyperosmolar Crisis / Diabetic Ketoacidosis (DKA/HHS):
    Severe acute dysglycemia with dehydration and metabolic decompensation.
    """

    def __init__(self):
        super().__init__(name="Hyperosmolar Crisis / DKA")

    def evaluate(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> PatternMatch:
        criteria: List[str] = []
        glu = vitals.get('glucose_max') or vitals.get('glucose_mean') or vitals.get('glucose')
        ph = vitals.get('ph_min') or vitals.get('ph_mean') or vitals.get('ph')
        na = vitals.get('sodium_mean') or vitals.get('sodium_max') or vitals.get('sodium')

        def to_f(v):
            try: return float(v) if v is not None else None
            except: return None

        glu = to_f(glu)
        ph = to_f(ph)
        na = to_f(na)

        cfg = PATTERN_CONFIG['hyperosmolar_crisis']
        is_marked_hyperglycemia = glu is not None and glu >= cfg['glucose_cutoff']
        has_acidosis = ph is not None and ph < 7.30
        has_hypernatremia = na is not None and na >= 145.0

        if is_marked_hyperglycemia:
            criteria.append(f"Marked hyperglycemia (Glucose {glu:.0f} mg/dL >= {cfg['glucose_cutoff']} mg/dL)")
        if has_acidosis:
            criteria.append(f"Metabolic acidosis / DKA trigger (pH {ph:.2f} < 7.30)")
        if has_hypernatremia:
            criteria.append(f"Hyperosmolar dehydration marker (Sodium {na:.1f} mmol/L)")

        if is_marked_hyperglycemia and (has_acidosis or has_hypernatremia):
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="HIGH",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="DKA / HHS Protocol: Check serum ketones and effective osmolality; aggressive isotonic fluid resuscitation (1-1.5 L/hr NS initially); check potassium before starting regular insulin infusion (0.1 U/kg/h); monitor glucose hourly.",
                urgency_tier="IMMEDIATE"
            )
        elif is_marked_hyperglycemia:
            return PatternMatch(
                pattern_name=self.name,
                detected=True,
                confidence="MODERATE",
                diagnostic_criteria_met=criteria,
                clinical_recommendation="Severe hyperglycemia: Check beta-hydroxybutyrate and urine ketones, titrate intravenous insulin protocol, monitor electrolytes and fluid balance.",
                urgency_tier="URGENT"
            )

        return PatternMatch(
            pattern_name=self.name,
            detected=False,
            confidence="NONE",
            diagnostic_criteria_met=[],
            clinical_recommendation="No overt hyperosmolar or ketoacidotic crisis detected.",
            urgency_tier="ROUTINE"
        )

