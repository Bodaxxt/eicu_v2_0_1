"""
ICU Guard v5.0 — SBAR Clinical Shift Handoff Generator
======================================================
Produces structured, standardized nursing and intensivist shift handoff reports:
- Situation: Patient triage tier, acute status, and chief concern
- Background: Comorbidities, unit admission pathway, and baseline parameters
- Assessment: Multi-organ failure breakdown, active patterns, and ML trajectory
- Recommendation: Immediate bedside tasks, monitoring frequency, and escalation triggers
"""

from typing import Dict, Any, Optional
import json

from severity_agent.llm_copilot.client import LLMClient
from severity_agent.llm_copilot.safety import PHIScrubber, stamp_advisory


class SBARGenerator:
    """Generates standardized SBAR clinical handoff documentation."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def generate(
        self,
        assessment_summary: Dict[str, Any],
        patient_vitals: Dict[str, Any],
        shift_notes: str = ""
    ) -> str:
        """Produce structured SBAR handoff report."""
        clean_vitals = PHIScrubber.sanitize_features(patient_vitals)

        tier = assessment_summary.get('severity_tier', 'MODERATE')
        score = assessment_summary.get('overall_score', 5.0)
        trajectory = assessment_summary.get('trajectory', 'STABLE')
        primary = assessment_summary.get('primary_etiology', 'Systemic Stress')
        red_flags = assessment_summary.get('active_red_flags', [])
        patterns = [p.get('name') for p in assessment_summary.get('patterns', [])]
        recommended_action = assessment_summary.get('recommended_action', 'Continue monitoring.')

        # Extract vital sign snapshots
        hr = clean_vitals.get('heartrate_mean', 'N/A')
        bp = clean_vitals.get('meanbp_min', 'N/A')
        rr = clean_vitals.get('respiration_max', 'N/A')
        sao2 = clean_vitals.get('sao2_min', 'N/A')
        cr = clean_vitals.get('creatinine_max', 'N/A')
        lactate = clean_vitals.get('lactate_max', 'N/A')

        # Comorbidities
        comorbs = []
        if clean_vitals.get('has_diabetes') == 1: comorbs.append("Diabetes Mellitus")
        if clean_vitals.get('has_hypertension') == 1: comorbs.append("Hypertension")
        if clean_vitals.get('has_chf') == 1: comorbs.append("Congestive Heart Failure")
        if clean_vitals.get('has_copd') == 1: comorbs.append("COPD")
        if clean_vitals.get('has_ckd') == 1: comorbs.append("Chronic Kidney Disease")
        comorb_str = ", ".join(comorbs) if comorbs else "No major chronic comorbidities documented"

        # Deterministic SBAR template
        sbar_text = f"""
================================================================================
  SBAR CRITICAL CARE SHIFT HANDOFF REPORT
================================================================================
[S] SITUATION:
- Patient Triage Level: {tier} (Composite Severity Score: {score:.1f}/10.0)
- Current Trajectory: {trajectory}
- Primary Clinical Concern: {primary}
- Red Flag Life Threats: {'; '.join(red_flags) if red_flags else 'None active'}

[B] BACKGROUND:
- Baseline Comorbidities: {comorb_str}
- Supportive Interventions: {'Vasopressor Infusion Active' if clean_vitals.get('vasopressor_6h') == 1 else 'No continuous vasopressors'}; {'Mechanical Ventilation Active' if clean_vitals.get('ventilation_6h') == 1 else 'Spontaneously breathing'}
- Additional Shift Notes: {shift_notes if shift_notes else 'Standard ICU surveillance'}

[A] ASSESSMENT:
- Bedside Telemetry Snapshot: HR Mean={hr} bpm | MAP Min={bp} mmHg | RR Max={rr} /min | SaO2 Min={sao2}%
- Laboratory Clearance: Serum Creatinine Max={cr} mg/dL | Serum Lactate Max={lactate} mmol/L
- Active Clinical Syndromes: {', '.join(patterns) if patterns else 'No complex syndromic patterns detected'}
- Subsystem Integrity: Evaluated across 11 physiological organ systems.

[R] RECOMMENDATION:
- Immediate Priority: {recommended_action}
- Monitoring Frequency: Vital signs q1h; repeat arterial blood gas and lactate in 2-4 hours.
- Escalation Triggers: Notify on-call intensivist if MAP < 65 mmHg, Urine output < 0.5 mL/kg/h for 2 consecutive hours, or SaO2 < 90%.
================================================================================
"""
        return stamp_advisory(sbar_text.strip())
