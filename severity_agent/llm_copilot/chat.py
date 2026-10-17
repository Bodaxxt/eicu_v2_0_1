"""
ICU Guard v5.0 — LLM Copilot Bedside Clinical Chat
==================================================
Conversational interface allowing critical care clinicians to query patient physiological status,
guidelines, medication dosing adjustments, and differential rationale.

Features:
- Dual-Mode: Online AI generation (OpenAI, Azure, Gemini, Ollama) + Pure Python fallback.
- Context-grounded responses rooted in the current patient's vital signs and organ assessments.
- Strict Zero-PHI enforcement before any remote inference.
- Multi-turn clinical conversation support.
"""

from typing import Dict, Any, List, Optional
import json
import logging

from severity_agent.llm_copilot.client import BaseLLMClient, AutoClient, LLMClient, AUTO_FALLBACK_MARKER
from severity_agent.llm_copilot.safety import PHIScrubber, stamp_advisory

logger = logging.getLogger(__name__)


class BedsideClinicalChat:
    """Answers physician queries regarding patient status, lab interpretation, and guidelines."""

    def __init__(self, client: Optional[BaseLLMClient] = None):
        self.client = client or AutoClient()
        self.history: List[Dict[str, str]] = []

    def reset_session(self):
        """Clear conversation history for a new clinical session."""
        self.history.clear()

    def ask(
        self,
        question: str,
        assessment_summary: Dict[str, Any],
        patient_vitals: Dict[str, Any],
        include_history: bool = True
    ) -> str:
        """
        Process a clinician query using current patient telemetry and reasoning context.
        Attempts online generation first; falls back seamlessly to deterministic clinical rules.
        """
        clean_vitals = PHIScrubber.sanitize_features(patient_vitals)

        prompt = f"""
[PATIENT PHYSIOLOGICAL CONTEXT]
- Severity Tier: {assessment_summary.get('severity_tier')}
- Trajectory: {assessment_summary.get('trajectory')}
- Primary Etiology: {assessment_summary.get('primary_etiology')}
- Active Red Flags: {assessment_summary.get('active_red_flags')}
- Current Vitals & Labs:
{json.dumps({k: v for k, v in clean_vitals.items() if v is not None and not str(v).lower() == 'nan'}, indent=2)}

[CONVERSATION HISTORY]
{self._format_history() if include_history and self.history else "None (New Session)"}

[PHYSICIAN QUESTION]
{question}

Provide a direct, authoritative critical care response backed by established guidelines (SSC 2021, KDIGO, Berlin).
Be concise, evidence-based, and focused on patient safety.
"""
        system = (
            "You are an ICU Clinical Copilot providing evidence-based bedside answers to treating critical care physicians. "
            "Prioritize patient stabilization, physiological rationale, and protocol adherence. Always maintain advisory tone."
        )

        # 1. Online Execution Attempt
        if self.client.is_online:
            try:
                response = self.client.complete(prompt, system_prompt=system)
                if response and len(response.strip()) > 10:
                    # Detect if AutoClient itself fell back to its generic deterministic
                    # synthesis (e.g. due to 429 / network failure) — in that case use
                    # BedsideClinicalChat's own richer deterministic answer instead.
                    if AUTO_FALLBACK_MARKER not in response:
                        self.history.append({"role": "user", "content": question})
                        self.history.append({"role": "assistant", "content": response})
                        return response
            except Exception as e:
                logger.warning(
                    f"BedsideClinicalChat: Online query failed on {getattr(self.client, 'provider_name', 'LLM')}: {e}. "
                    "Falling back to pure Python clinical rules."
                )

        # 2. Pure Python Offline Fallback (Guaranteed Resilience)
        offline_ans = self._deterministic_answer(question, assessment_summary, clean_vitals)
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": offline_ans})
        return offline_ans

    def _deterministic_answer(
        self,
        question: str,
        assessment_summary: Dict[str, Any],
        vitals: Dict[str, Any]
    ) -> str:
        """Produce deterministic, guidelines-grounded response for common critical care questions."""
        q_lower = question.lower()
        tier = assessment_summary.get('severity_tier', 'MODERATE')
        primary = assessment_summary.get('primary_etiology', 'Systemic Stress')
        red_flags = assessment_summary.get('active_red_flags', [])

        if "fluid" in q_lower or "bolus" in q_lower:
            ans = (
                "Surviving Sepsis guidelines recommend 30 mL/kg balanced crystalloids for septic hypoperfusion "
                "within the first 3 hours. Subsequent resuscitation should be guided by dynamic measures of fluid "
                "responsiveness (passive leg raise or stroke volume variation) to prevent pulmonary edema."
            )
        elif "antibiotic" in q_lower or "culture" in q_lower or "infection" in q_lower:
            ans = (
                "Administer empiric broad-spectrum IV antimicrobials immediately (within 1 hour) after drawing two sets "
                "of blood cultures (aerobic and anaerobic). Narrow therapy once microbiology data return."
            )
        elif "vasopressor" in q_lower or "map" in q_lower or "norepinephrine" in q_lower or "blood pressure" in q_lower:
            ans = (
                "First-line vasopressor is Norepinephrine titrated to maintain target MAP >= 65 mmHg. If norepinephrine "
                "requirements escalate (> 0.25 mcg/kg/min), add Vasopressin at a fixed dose of 0.03 units/min. Place an arterial line."
            )
        elif "kdigo" in q_lower or "renal" in q_lower or "dialysis" in q_lower or "creatinine" in q_lower:
            ans = (
                "For KDIGO AKI, immediately discontinue nephrotoxic agents, optimize renal perfusion pressure (target MAP >= 65-70 mmHg), "
                "maintain strict hourly urine output monitoring. Indications for emergent RRT include refractory hyperkalemia (K > 6.5), "
                "refractory acidemia (pH < 7.15), and uremic encephalopathy."
            )
        elif "why" in q_lower and ("tier" in q_lower or "escalat" in q_lower or "critical" in q_lower):
            ans = (
                f"The patient was assigned to tier **{tier}** primarily due to: {primary}. "
                f"{'Active red flags: ' + ', '.join(red_flags) + '. ' if red_flags else ''}"
                "The safety arbitration engine ensures high-acuity organ injury and vital instability automatically override "
                "baseline model probabilities to prevent false-negative underestimation."
            )
        else:
            ans = (
                f"Patient is currently staged at **{tier}** severity with primary etiology: **{primary}**. "
                f"{'Immediate life-threat red flags active: ' + '; '.join(red_flags) if red_flags else 'No single catastrophic red flag breached.'} "
                "Critical care guidelines mandate continuous telemetry monitoring, serial lactate and blood gas review q2-4h, "
                "and proactive application of organ-protective resuscitation bundles."
            )

        provider_note = getattr(self.client, 'provider_name', 'PurePythonOffline')
        return stamp_advisory(
            f"### CLINICAL COPILOT RESPONSE (BACKEND: {provider_note.upper()})\n\n"
            f"**Query:** {question}\n\n"
            f"**Response:** {ans}"
        )

    def _format_history(self) -> str:
        """Format recent dialogue for multi-turn context."""
        recent = self.history[-4:]
        lines = []
        for msg in recent:
            role = "Clinician" if msg["role"] == "user" else "Copilot"
            content = msg["content"]
            # Strip watermarks from previous messages in history for token efficiency
            content_clean = content.split("### CLINICAL COPILOT RESPONSE")[-1].strip() if "###" in content else content[:150]
            lines.append(f"{role}: {content_clean[:180]}")
        return "\n".join(lines)
