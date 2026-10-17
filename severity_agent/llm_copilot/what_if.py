"""
ICU Guard v5.0 — LLM Copilot What-If Scenario Simulator
========================================================
Narrates pathophysiological consequences and clinical trajectories under hypothetical bedside interventions:
- What if fluid resuscitation is administered vs held?
- What if inotropes are initiated?
- What if MAP target is elevated from 55 to 65 mmHg?
- What if invasive mechanical ventilation is delayed?
"""

from typing import Dict, Any, Optional
import json

from severity_agent.llm_copilot.client import LLMClient, AUTO_FALLBACK_MARKER
from severity_agent.llm_copilot.safety import PHIScrubber, stamp_advisory


class WhatIfSimulator:
    """Simulates clinical repercussions of hypothetical interventions."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def simulate(
        self,
        intervention_scenario: str,
        assessment_summary: Dict[str, Any],
        patient_vitals: Dict[str, Any]
    ) -> str:
        """Evaluate hypothetical intervention scenario against patient physiology."""
        clean_vitals = PHIScrubber.sanitize_features(patient_vitals)

        prompt = f"""
[CURRENT PATIENT STATE]
- Severity Tier: {assessment_summary.get('severity_tier')}
- Primary Etiology: {assessment_summary.get('primary_etiology')}
- Trajectory: {assessment_summary.get('trajectory')}
- Active Syndromes: {[p.get('name') for p in assessment_summary.get('patterns', [])]}
- Current Hemodynamics: MAP Min={clean_vitals.get('meanbp_min')}, HR={clean_vitals.get('heartrate_mean')}, Lactate={clean_vitals.get('lactate_max')}
- Current Respiratory: SaO2={clean_vitals.get('sao2_min')}, RR={clean_vitals.get('respiration_max')}

[HYPOTHETICAL INTERVENTION TO SIMULATE]
"{intervention_scenario}"

Please analyze:
1. Expected Immediate Physiological Response (Hemodynamics, Oxygenation, Perfusion)
2. Downstream Organ Repercussions (Renal clearance, myocardial workload, pulmonary edema risk)
3. Potential Adverse Risks or Contraindications of this intervention
4. Recommended Bedside Monitoring Parameters to verify safety
"""
        system = "You are a Critical Care Intensivist simulating pathophysiological counterfactuals for clinical decision support."

        if not getattr(self.client, 'is_online', False):
            return self._deterministic_simulate(intervention_scenario)

        response = self.client.complete(prompt, system_prompt=system)
        # Detect AutoClient generic fallback (e.g. API 429 / network error)
        if AUTO_FALLBACK_MARKER in response:
            return self._deterministic_simulate(intervention_scenario)
        return response

    def _deterministic_simulate(self, intervention_scenario: str) -> str:
        """Deterministic simulation template for common ICU scenarios."""
        scenario_lower = intervention_scenario.lower()
        if "fluid" in scenario_lower or "crystalloid" in scenario_lower:
            effect = "Volume expansion will augment end-diastolic ventricular filling and preload. However, if the patient has impaired cardiac contractility or acute lung injury, fluid administration carries high risk of extravasation into pulmonary interstitium, worsening hypoxemic ARDS."
            risks = "Pulmonary edema, increased ventilator days, elevated intra-abdominal pressure, impaired renal venous return."
            monitoring = "Serial lung ultrasound for B-lines, stroke volume variation, passive leg raise test."
        elif "norepinephrine" in scenario_lower or "vasopressor" in scenario_lower:
            effect = "Potent alpha-1 vasoconstriction increases systemic vascular resistance, elevating MAP >= 65 mmHg and restoring coronary and renal perfusion pressure."
            risks = "Excessive vasoconstriction in hypovolemic patients may worsen peripheral ischemia; reflex bradycardia or tachyarrhythmias."
            monitoring = "Continuous arterial line blood pressure, peripheral perfusion index, serial lactate clearance."
        elif "intubat" in scenario_lower or "ventilator" in scenario_lower:
            effect = "Positive pressure ventilation relieves work of breathing, eliminates metabolic cost of tachypnea, secures the airway, and allows precise control of PEEP and FiO2."
            risks = "Hypotension on induction due to sympathetic tone loss and increased intrathoracic pressure impeding venous return; ventilator-induced lung injury (VILI)."
            monitoring = "Post-intubation MAP, plateau pressure (< 30 cmH2O), driving pressure (< 15 cmH2O), endotracheal cuff pressure."
        else:
            effect = f"Applying the intervention '{intervention_scenario}' alters physiological loading conditions and neurohormonal reflex arcs."
            risks = "Risk of unintended secondary organ stress if unmonitored."
            monitoring = "Continuous vital signs, telemetry, and serial blood gases."

        narrative = f"""
### WHAT-IF SCENARIO CLINICAL SIMULATION (DETERMINISTIC)
**Hypothetical Scenario:** "{intervention_scenario}"

**1. Expected Physiological Response:**
{effect}

**2. Secondary Organ Impact & Adverse Risks:**
{risks}

**3. Recommended Bedside Safety Monitoring:**
{monitoring}
"""
        return stamp_advisory(narrative.strip())
