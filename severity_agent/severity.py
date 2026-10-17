"""
ICU Guard v4.2 — Severity Evaluator & Safety Override Engine
============================================================
Computes final patient clinical triage tier (STABLE, MODERATE, HIGH, CRITICAL)
by combining:
1. Multi-Target ML Probabilities (Mortality, Deterioration, Severity)
2. Organ System Failure Burden (Max organ grade, count of compromised organs)
3. Pattern Multi-System Syndromes (Septic Shock, ARDS, MOF)
4. Absolute Physiological Red Flags (Safety Overrides that force CRITICAL status)

CLINICAL SAFETY PRINCIPLE:
The Safety Override Engine is strictly non-downgrading. It can escalate a patient's
triage tier (e.g. from MODERATE to CRITICAL upon discovering MAP < 50), but will
NEVER demote a patient to a lower tier than what machine learning risk thresholds prescribe.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math
import logging

from severity_agent.detectors import OrganAssessment
from severity_agent.patterns import PatternMatch
from severity_agent.config import (
    SEVERITY_LEVELS,
    SEVERITY_ORDER,
    ABSOLUTE_RED_FLAGS,
    ML_PROBABILITY_THRESHOLDS
)

logger = logging.getLogger(__name__)


@dataclass
class SeverityAssessment:
    """Final clinical severity classification and escalation audit."""
    final_tier: str                  # "STABLE", "MODERATE", "HIGH", "CRITICAL"
    ml_base_tier: str                # Baseline tier purely from ML probabilities
    organ_driven_tier: str           # Tier indicated by organ failure burden
    escalation_occurred: bool        # True if safety override or organ rule bumped tier
    escalation_reasons: List[str] = field(default_factory=list)
    active_red_flags: List[str] = field(default_factory=list)
    overall_score: float = 0.0       # Composite severity index (0.0 to 10.0)
    recommended_clinical_action: str = ""

    @property
    def is_critical(self) -> bool:
        return self.final_tier == "CRITICAL"


class SeverityEvaluator:
    """Evaluates multi-modal physiological severity with non-downgrading safety guarantees."""

    def __init__(self):
        self.levels = SEVERITY_LEVELS
        self.order = SEVERITY_ORDER

    def evaluate(
        self,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        vitals: Dict[str, Any]
    ) -> SeverityAssessment:
        """
        Synthesize multi-modal severity and apply absolute safety overrides.
        
        Args:
            probabilities: Dict with 'p_mortality', 'p_deterioration', 'p_severe'
            organ_assessments: Dict of organ assessments from organ detectors
            patterns: List of detected clinical syndrome patterns
            vitals: Raw patient vital signs and lab values
        """
        escalation_reasons: List[str] = []
        active_red_flags: List[str] = []

        p_m = probabilities.get('p_mortality', 0.0)
        p_d = probabilities.get('p_deterioration', 0.0)
        p_s = probabilities.get('p_severe', 0.0)

        # -------------------------------------------------------------
        # 1. Base Machine Learning Triage Tier
        # -------------------------------------------------------------
        # Pipeline rules:
        # CRITICAL: p_mortality > 0.70 or p_deterioration > 0.85
        # HIGH: p_mortality > 0.40 or p_deterioration > 0.50
        # MODERATE: p_severe > 0.50 or p_deterioration > 0.30 or p_mortality > 0.20
        # STABLE: Default
        ml_cfg = ML_PROBABILITY_THRESHOLDS
        if p_m > ml_cfg['mortality']['critical'] or p_d > ml_cfg['deterioration']['critical']:
            ml_tier = "CRITICAL"
        elif p_m > ml_cfg['mortality']['high'] or p_d > ml_cfg['deterioration']['high']:
            ml_tier = "HIGH"
        elif p_s > ml_cfg['severe']['moderate'] or p_d > ml_cfg['deterioration']['moderate'] or p_m > ml_cfg['mortality']['moderate']:
            ml_tier = "MODERATE"
        else:
            ml_tier = "STABLE"

        # -------------------------------------------------------------
        # 2. Physiological Organ Burden Triage Tier
        # -------------------------------------------------------------
        max_organ_grade = max((a.grade for a in organ_assessments.values()), default=0)
        compromised_organs_count = sum(1 for a in organ_assessments.values() if a.grade >= 1)
        critical_organs_count = sum(1 for a in organ_assessments.values() if a.grade >= 2)

        if max_organ_grade >= 3 or critical_organs_count >= 2:
            organ_tier = "CRITICAL"
        elif max_organ_grade == 2 or compromised_organs_count >= 2:
            organ_tier = "HIGH"
        elif max_organ_grade == 1:
            organ_tier = "MODERATE"
        else:
            organ_tier = "STABLE"

        # -------------------------------------------------------------
        # 3. Check Absolute Red Flags (Mandate Immediate CRITICAL)
        # -------------------------------------------------------------
        red_flags_triggered = self._check_red_flags(vitals)
        if red_flags_triggered:
            active_red_flags.extend(red_flags_triggered)
            escalation_reasons.extend(red_flags_triggered)

        # -------------------------------------------------------------
        # 4. Check Pattern Syndrome Escalate
        # -------------------------------------------------------------
        for pat in patterns:
            if pat.detected and pat.urgency_tier == "IMMEDIATE":
                escalation_reasons.append(f"Syndrome Escalation: {pat.pattern_name} detected ({pat.confidence} confidence).")

        # -------------------------------------------------------------
        # 5. Non-Downgrading Triage Arbitration
        # -------------------------------------------------------------
        # Start with ML tier
        candidate_tier = ml_tier

        # If organ burden is higher, escalate
        if self.order[organ_tier] > self.order[candidate_tier]:
            escalation_reasons.append(
                f"Organ Burden Escalation: {critical_organs_count} critical organs (Max Grade {max_organ_grade}) escalated tier from {candidate_tier} to {organ_tier}."
            )
            candidate_tier = organ_tier

        # If any absolute red flag is present, force CRITICAL
        if active_red_flags or any(pat.detected and pat.urgency_tier == "IMMEDIATE" for pat in patterns):
            if candidate_tier != "CRITICAL":
                escalation_reasons.append(f"Safety Override: Tier forced to CRITICAL due to absolute life-threat conditions.")
            candidate_tier = "CRITICAL"

        escalation_occurred = (candidate_tier != ml_tier)

        # -------------------------------------------------------------
        # 6. Composite Severity Index (0.0 to 10.0 scale)
        # -------------------------------------------------------------
        # 40% ML Max Prob + 40% Max Organ Grade (normalized to 1) + 20% Organ Burden
        max_prob = max(p_m, p_d, p_s)
        total_organs = max(1, len(organ_assessments))
        organ_ratio = min(1.0, compromised_organs_count / float(total_organs))
        grade_ratio = max_organ_grade / 3.0
        composite_score = round(
            (max_prob * 4.0) + (grade_ratio * 4.0) + (organ_ratio * 2.0),
            2
        )
        # If red flag is present, ensure composite score is at least 8.5
        if active_red_flags and composite_score < 8.5:
            composite_score = 8.5

        # Actions map
        action_map = {
            "CRITICAL": "Immediate intensivist bedside arrival; prepare emergency intubation / invasive lines; active resuscitation bundle.",
            "HIGH":     "Urgent clinical evaluation within 15 minutes; repeat blood gas; step-down or ICU bed allocation; strict hemodynamic monitoring.",
            "MODERATE": "Enhanced surveillance; repeat vital signs hourly; evaluate fluid response and renal clearance trends.",
            "STABLE":   "Maintain standard ICU protocol; continue scheduled medication and routine vital signs observation."
        }

        return SeverityAssessment(
            final_tier=candidate_tier,
            ml_base_tier=ml_tier,
            organ_driven_tier=organ_tier,
            escalation_occurred=escalation_occurred,
            escalation_reasons=escalation_reasons,
            active_red_flags=active_red_flags,
            overall_score=composite_score,
            recommended_clinical_action=action_map[candidate_tier]
        )

    def _check_red_flags(self, vitals: Dict[str, Any]) -> List[str]:
        """Scan for critical red flags that mandate immediate emergency escalation."""
        flags: List[str] = []
        cfg = ABSOLUTE_RED_FLAGS

        def get_v(*keys):
            for k in keys:
                if k in vitals:
                    val = vitals[k]
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            continue
            return None

        # GCS <= 8
        gcs = get_v('gcs_min', 'gcs_mean', 'gcs')
        if gcs is not None and gcs <= cfg.get('gcs_min', 8.0):
            flags.append(f"ABSOLUTE RED FLAG: Coma / Airway loss (GCS {gcs:.0f} <= {cfg['gcs_min']:.0f})")

        # MAP < 50
        map_val = get_v('meanbp_min', 'meanbp_mean', 'meanbp')
        if map_val is not None and map_val < cfg.get('meanbp_min', 50.0):
            flags.append(f"ABSOLUTE RED FLAG: Profound cerebral/renal hypoperfusion (MAP {map_val:.1f} mmHg < {cfg['meanbp_min']} mmHg)")

        # SBP < 70
        sbp = get_v('sbp_min', 'sbp_mean', 'sbp')
        if sbp is not None and sbp < cfg.get('sbp_min', 70.0):
            flags.append(f"ABSOLUTE RED FLAG: Cardiovascular collapse (SBP {sbp:.1f} mmHg < {cfg['sbp_min']} mmHg)")

        # SaO2 < 50 or PaO2 < 50
        sao2 = get_v('sao2_min', 'sao2_mean', 'sao2')
        if sao2 is not None and sao2 < cfg.get('sao2_min', 50.0):
            flags.append(f"ABSOLUTE RED FLAG: Catastrophic hypoxemia (SaO2 {sao2:.1f}% < {cfg['sao2_min']}%)")

        pao2 = get_v('pao2_min', 'pao2_mean', 'pao2')
        if pao2 is not None and pao2 < cfg.get('pao2_min', 50.0):
            flags.append(f"ABSOLUTE RED FLAG: Critical anoxia (PaO2 {pao2:.1f} mmHg < {cfg['pao2_min']} mmHg)")

        # Lactate > 8
        lactate = get_v('lactate_max', 'lactate_mean', 'lactate')
        if lactate is not None and lactate > cfg.get('lactate_max', 8.0):
            flags.append(f"ABSOLUTE RED FLAG: Severe lactic acidosis / metabolic shutdown (Lactate {lactate:.1f} mmol/L > {cfg['lactate_max']} mmol/L)")

        # pH < 7.10
        ph = get_v('ph_min', 'ph_mean', 'ph')
        if ph is not None and ph < cfg.get('ph_min', 7.10):
            flags.append(f"ABSOLUTE RED FLAG: Severe acidemia (pH {ph:.2f} < {cfg['ph_min']})")

        # Glucose <= 40
        glu = get_v('glucose_min', 'glucose_mean', 'glucose')
        if glu is not None and 'glucose_min' in cfg and glu <= cfg['glucose_min']:
            flags.append(f"ABSOLUTE RED FLAG: Severe neuroglycopenia (Glucose {glu:.0f} mg/dL <= {cfg['glucose_min']} mg/dL)")

        # Platelets <= 20
        plt = get_v('platelets_min', 'platelets_mean', 'platelets')
        if plt is not None and 'platelets_min' in cfg and plt <= cfg['platelets_min']:
            flags.append(f"ABSOLUTE RED FLAG: Spontaneous intracranial hemorrhage risk (Platelets {plt:.0f} <= {cfg['platelets_min']} x10^9/L)")

        # Potassium >= 6.5 or <= 2.5
        k_val = get_v('potassium_max', 'potassium_mean', 'potassium')
        if k_val is not None and 'potassium_max' in cfg and k_val >= cfg['potassium_max']:
            flags.append(f"ABSOLUTE RED FLAG: Critical hyperkalemia cardiac arrest risk (Potassium {k_val:.1f} >= {cfg['potassium_max']} mmol/L)")

        k_min = get_v('potassium_min')
        if k_min is not None and 'potassium_min' in cfg and k_min <= cfg['potassium_min']:
            flags.append(f"ABSOLUTE RED FLAG: Severe hypokalemic arrhythmia risk (Potassium {k_min:.1f} <= {cfg['potassium_min']} mmol/L)")

        return flags
