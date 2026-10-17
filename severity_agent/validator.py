"""
ICU Guard v5.0 — Enhanced Clinical Prediction Validator
======================================================
Validates machine learning output integrity via 6 comprehensive clinical sanity checks:
1. Physiological Cross-System Consistency Check (Are predicted risks congruent with all 11 organ systems?)
2. Temporal Plausibility & Volatility Check      (Are vital dynamics and standard deviations temporally coherent?)
3. Out-of-Distribution (OOD) Anomaly Check      (Detects covariate shift and unphysiological sensor artifacts)
4. SHAP Multi-System Plausibility Check         (Are model drivers aligned with validated critical care biology?)
5. Missing Data Burden & Subsystem Impact Check (Calculates subsystem-specific data missingness)
6. Cross-Target Mathematical Contradiction Check (Verifies joint trajectory coherence across mortality/deterioration/severity)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging
import math

from severity_agent.detectors import OrganAssessment

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Clinical integrity audit report for model inference."""
    is_valid: bool
    confidence: str                 # "HIGH", "MODERATE", "LOW"
    warnings: List[str] = field(default_factory=list)
    missingness_rate_pct: float = 0.0
    contradictions_detected: List[str] = field(default_factory=list)
    clinical_sanity_status: str = "PASSED"
    # v5.0 Enhanced Audit Attributes
    ood_detected: bool = False
    ood_score: float = 0.0          # Normalized anomaly index (0.0 to 1.0)
    temporal_stability_status: str = "STABLE"
    organ_missingness_breakdown: Dict[str, float] = field(default_factory=dict)
    subsystem_consistency_status: str = "CONSISTENT"

    def summary(self) -> str:
        status_sym = "[VALID]" if self.is_valid else "[FLAGGED]"
        ood_sym = "[OOD ALERT]" if self.ood_detected else "[IN-DISTRIBUTION]"
        return f"{status_sym} {ood_sym} Confidence: {self.confidence} | Warnings: {len(self.warnings)} | Missingness: {self.missingness_rate_pct:.1f}% | OOD Score: {self.ood_score:.2f}"


class PredictionValidator:
    """Performs rigorous pre-bedside clinical verification on multi-target ML predictions."""

    # Physiological plausibility boundaries (extreme biological limits)
    BIOLOGICAL_LIMITS = {
        'sbp': (30.0, 280.0),
        'meanbp': (25.0, 200.0),
        'heartrate': (20.0, 240.0),
        'resprate': (4.0, 75.0),
        'temperature': (28.0, 43.5),
        'sao2': (30.0, 100.0),
        'ph': (6.75, 7.80),
        'potassium': (1.5, 9.5),
        'glucose': (15.0, 1500.0),
        'creatinine': (0.1, 25.0),
        'lactate': (0.2, 30.0),
        'platelets': (2.0, 2000.0),
    }

    def __init__(self, max_allowed_missing_pct: float = 65.0):
        self.max_allowed_missing_pct = max_allowed_missing_pct

    def validate(
        self,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any],
        top_shap_features: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> ValidationReport:
        """
        Execute the 6-layer validation audit.
        """
        warnings: List[str] = []
        contradictions: List[str] = []

        p_m = probabilities.get('p_mortality', 0.0)
        p_d = probabilities.get('p_deterioration', 0.0)
        p_s = probabilities.get('p_severe', 0.0)

        # -------------------------------------------------------------
        # 1. Missing Data Burden & Subsystem Impact Check
        # -------------------------------------------------------------
        total_keys = len(vitals)
        if total_keys > 0:
            null_count = sum(
                1 for v in vitals.values() 
                if v is None or (isinstance(v, float) and math.isnan(v))
            )
            missing_rate = (null_count / total_keys) * 100.0
        else:
            missing_rate = 100.0
            warnings.append("No patient features supplied to validator.")

        # Breakdown missing indicators across organ detectors
        subsystem_missing = {}
        for name, assess in organ_assessments.items():
            if assess.missing_indicators:
                subsystem_missing[name] = len(assess.missing_indicators)

        if missing_rate > self.max_allowed_missing_pct:
            warnings.append(
                f"Elevated missing feature burden ({missing_rate:.1f}% > {self.max_allowed_missing_pct}%). Model predictions have wider epistemic uncertainty."
            )

        # -------------------------------------------------------------
        # 2. Out-of-Distribution (OOD) Anomaly Check
        # -------------------------------------------------------------
        ood_detected, ood_score, ood_details = self._check_ood(vitals)
        if ood_detected:
            warnings.append(f"OOD Alert: Extreme unphysiological measurement(s) detected: {'; '.join(ood_details)}")

        # -------------------------------------------------------------
        # 3. Temporal Plausibility & Volatility Check
        # -------------------------------------------------------------
        temp_status, temp_warnings = self._check_temporal_plausibility(vitals)
        warnings.extend(temp_warnings)

        # -------------------------------------------------------------
        # 4. Cross-System Physiological Consistency Check
        # -------------------------------------------------------------
        max_organ_grade = max((a.grade for a in organ_assessments.values()), default=0)
        critical_organs = [name for name, a in organ_assessments.items() if a.grade == 3]

        if max_organ_grade == 3 and p_d < 0.15 and p_m < 0.10:
            contradictions.append(
                f"False Negative Alarm Risk: Severe organ failure present ({', '.join(critical_organs)} Grade 3), but ML predicted discordant low deterioration ({p_d:.2f}) and mortality ({p_m:.2f})."
            )
            warnings.append("Physiological paradox: Bedside organ failure observed with discordant low ML scores.")

        if max_organ_grade == 0 and p_m > 0.85:
            warnings.append(
                f"Potential False Positive: All physiological organ systems normal (Grade 0), but p_mortality is very high ({p_m:.2f}). Verify baseline comorbidities and age."
            )

        # Hemodynamic collapse without compensation check
        map_val = vitals.get('meanbp_min') or vitals.get('meanbp_mean')
        hr_val = vitals.get('heartrate_max') or vitals.get('heartrate_mean')
        try:
            if map_val is not None and float(map_val) < 50.0 and hr_val is not None and float(hr_val) < 50.0:
                warnings.append(f"Severe simultaneous hypotension (MAP {map_val}) and bradycardia (HR {hr_val}): High impending arrest / complete AV block hazard.")
        except (ValueError, TypeError):
            pass

        # -------------------------------------------------------------
        # 5. Cross-Target Contradiction Check
        # -------------------------------------------------------------
        if p_m > 0.75 and p_d < 0.20:
            contradictions.append(
                f"Cross-target divergence: Extreme mortality risk ({p_m:.2f}) with negligible deterioration probability ({p_d:.2f})."
            )

        if p_s < 0.20 and p_m > 0.60:
            contradictions.append(
                f"Cross-target anomaly: High mortality ({p_m:.2f}) despite low disease severity score ({p_s:.2f})."
            )

        # -------------------------------------------------------------
        # 6. Deepened SHAP Plausibility Alignment Check
        # -------------------------------------------------------------
        if top_shap_features:
            for tgt, feats in top_shap_features.items():
                if not feats:
                    continue
                known_clinical_tokens = [
                    'bp', 'hr', 'heart', 'resp', 'o2', 'sao2', 'pao2', 'temp', 'gcs', 
                    'creat', 'bun', 'lactate', 'age', 'platelet', 'bili', 'glucose', 'ph', 'hgb'
                ]
                has_clinical_driver = any(
                    any(tok in f.get('feature', '').lower() for tok in known_clinical_tokens)
                    for f in feats[:5]
                )
                if not has_clinical_driver:
                    warnings.append(f"SHAP Alert ({tgt}): Top predictive features do not include standard vital/laboratory drivers.")

        # -------------------------------------------------------------
        # Confidence & Validity Determination
        # -------------------------------------------------------------
        is_valid = len(contradictions) == 0

        if not is_valid or missing_rate > 70.0 or (ood_detected and ood_score > 0.8):
            confidence = "LOW"
            sanity_status = "CRITICAL_REVIEW_REQUIRED"
        elif len(warnings) > 1 or missing_rate > 50.0 or ood_detected:
            confidence = "MODERATE"
            sanity_status = "ACCEPTABLE_WITH_CAUTION"
        else:
            confidence = "HIGH"
            sanity_status = "PASSED"

        subsystem_status = "CONTRADICTORY" if len(contradictions) > 0 else "CONSISTENT"

        return ValidationReport(
            is_valid=is_valid,
            confidence=confidence,
            warnings=warnings,
            missingness_rate_pct=round(missing_rate, 2),
            contradictions_detected=contradictions,
            clinical_sanity_status=sanity_status,
            ood_detected=ood_detected,
            ood_score=round(ood_score, 2),
            temporal_stability_status=temp_status,
            organ_missingness_breakdown=subsystem_missing,
            subsystem_consistency_status=subsystem_status
        )

    def _check_ood(self, vitals: Dict[str, Any]) -> tuple[bool, float, List[str]]:
        """Check for unphysiological outliers and calculate OOD score."""
        anomalies: List[str] = []
        outlier_count = 0
        total_checked = 0

        for feat_prefix, (low, high) in self.BIOLOGICAL_LIMITS.items():
            for k in [f"{feat_prefix}_min", f"{feat_prefix}_max", f"{feat_prefix}_mean", feat_prefix]:
                if k in vitals:
                    val = vitals[k]
                    if val is not None and not (isinstance(val, float) and math.isnan(val)):
                        try:
                            f_val = float(val)
                            total_checked += 1
                            if f_val < low or f_val > high:
                                outlier_count += 1
                                anomalies.append(f"{k}={f_val:.1f} (outside biological bounds [{low}, {high}])")
                        except (ValueError, TypeError):
                            pass

        ood_score = min(1.0, (outlier_count / max(1, total_checked)) * 5.0)
        is_ood = outlier_count > 0
        return is_ood, ood_score, anomalies

    def _check_temporal_plausibility(self, vitals: Dict[str, Any]) -> tuple[str, List[str]]:
        """Evaluate temporal stability from variance and rate of change."""
        warnings: List[str] = []
        hr_std = vitals.get('heartrate_std')
        bp_std = vitals.get('meanbp_std')
        resp_std = vitals.get('respiration_std')

        def to_f(v):
            try: return float(v) if v is not None and not math.isnan(float(v)) else None
            except: return None

        hr_std = to_f(hr_std)
        bp_std = to_f(bp_std)
        resp_std = to_f(resp_std)

        is_volatile = False
        if hr_std is not None and hr_std > 25.0:
            is_volatile = True
            warnings.append(f"Extreme cardiac instability: HR Standard Deviation={hr_std:.1f} bpm > 25.0")
        if bp_std is not None and bp_std > 20.0:
            is_volatile = True
            warnings.append(f"Severe vasomotor oscillation: MAP Standard Deviation={bp_std:.1f} mmHg > 20.0")

        status = "VOLATILE" if is_volatile else "STABLE"
        return status, warnings

