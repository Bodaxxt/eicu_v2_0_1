"""
ICU Guard v5.0 — LLM Copilot Reviewer (Second Opinion Layer)
============================================================
Critiques the deterministic assessment, checks for clinical blind spots,
drug-disease interactions, and potential diagnostic anchoring bias.
"""

from typing import Dict, Any, Optional
import json

from severity_agent.llm_copilot.client import LLMClient, AUTO_FALLBACK_MARKER
from severity_agent.llm_copilot.safety import PHIScrubber, stamp_advisory


class ClinicalReviewer:
    """Provides an automated adjunctive second opinion on the pure Python assessment."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def review(
        self,
        assessment_summary: Dict[str, Any],
        patient_vitals: Dict[str, Any]
    ) -> str:
        """Evaluate the pure Python assessment and identify any clinical blind spots."""
        clean_vitals = PHIScrubber.sanitize_features(patient_vitals)

        prompt = f"""
You are an expert Intensivist reviewing a Clinical Decision Support System's assessment.
Critique the following automated evaluation and provide an objective second opinion.

[ASSESSMENT SUMMARY]
- Severity Tier: {assessment_summary.get('severity_tier')}
- Overall Score: {assessment_summary.get('overall_score')} / 10.0
- Active Red Flags: {assessment_summary.get('active_red_flags')}
- Primary Etiology: {assessment_summary.get('primary_etiology')}
- Trajectory: {assessment_summary.get('trajectory')}
- Active Syndromes: {[p.get('name') for p in assessment_summary.get('patterns', [])]}
- Differential Diagnoses: {[d.get('diagnosis') for d in assessment_summary.get('differential_diagnoses', [])]}

[PATIENT PHYSIOLOGICAL HIGHLIGHTS]
{json.dumps({k: v for k, v in clean_vitals.items() if v is not None and not str(v).lower() == 'nan'}, indent=2)}

Please address:
1. Agreement or disagreement with the assigned triage tier and primary etiology.
2. Any subtle clinical blind spots (e.g. occult bleeding, mixed shock state, electrolyte hazards).
3. Suggestions for specialized diagnostic workup (e.g. POCUS, specific lab assays).
Keep your review concise, evidence-based, and actionable.
"""
        system = "You are a Critical Care Specialist conducting a rigorous second-opinion review of an AI decision-support report."
        
        if not getattr(self.client, 'is_online', False):
            return self._deterministic_review(assessment_summary)

        response = self.client.complete(prompt, system_prompt=system)
        # Detect AutoClient generic fallback (e.g. API 429 / network error)
        if AUTO_FALLBACK_MARKER in response:
            return self._deterministic_review(assessment_summary)
        return response

    def _deterministic_review(self, assessment_summary: dict) -> str:
        """Specialist second-opinion in deterministic mode."""
        tier = assessment_summary.get('severity_tier', 'MODERATE')
        primary = assessment_summary.get('primary_etiology', 'Systemic Stress')
        flags = assessment_summary.get('active_red_flags', [])
        return stamp_advisory(
            f"### INTENSIVIST SECOND OPINION REVIEW (DETERMINISTIC MODE)\n\n"
            f"**1. Triage Tier Alignment:** Concur with tier **{tier}**. "
            f"The assigned severity reflects physiological organ burden and trajectory.\n\n"
            f"**2. Primary Etiology:** Assessed as **{primary}**. "
            f"{'Absolute red flags triggered: ' + '; '.join(flags) if flags else 'No contradictory red flags detected.'}\n\n"
            f"**3. Clinical Blind Spot Screening:**\n"
            f"- Ensure dynamic fluid responsiveness (passive leg raise or stroke volume variation) prior to indiscriminate volume loading.\n"
            f"- Screen for medication-induced nephrotoxicity or drug-drug interactions.\n"
            f"- Verify acid-base balance via repeat arterial blood gas in 2-4 hours.\n\n"
            f"**4. Diagnostic Recommendations:** Bedside focused cardiac & lung ultrasound (POCUS); monitor continuous urine output and serial lactate."
        )
