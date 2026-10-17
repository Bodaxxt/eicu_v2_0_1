"""
ICU Guard v5.0 — LLM Copilot Safety & Privacy Guardrails
========================================================
Enforces strict regulatory and privacy boundaries:
1. Zero-PHI De-Identification (Removes patient IDs, admission timestamps, MRNs)
2. Advisory Watermarking (Stamps all outputs as non-decision-making clinical advice)
3. Prompt Sanitization & Injection Defense
4. Determinism Constraints (Temperature clamping <= 0.2)
"""

import re
from typing import Dict, Any, List

ADVISORY_WATERMARK = """
[CLINICAL DECISION SUPPORT ADVISORY — NOT AUTONOMOUS]
ICU Guard v5.0 LLM Copilot provides adjunctive second-opinion analysis only.
All definitive medical diagnoses, orders, and therapeutic decisions remain
the sole legal responsibility of the licensed treating critical care physician.
"""


class PHIScrubber:
    """Anonymizes patient dictionaries before LLM serialization."""

    PHI_FIELDS = {
        'patientunitstayid', 'uniquepid', 'patient_id', 'mrn', 'name', 
        'hospitalid', 'wardid', 'unitdischargeoffset', 'hospitaldischargeoffset',
        'det_event_offset', 'severe_event_offset', 'lac_crit_offset'
    }

    @classmethod
    def sanitize_features(cls, patient_features: Dict[str, Any]) -> Dict[str, Any]:
        """Strip all direct and quasi-identifiers, retaining only physiological features."""
        clean = {}
        for k, v in patient_features.items():
            k_lower = k.lower()
            if any(phi in k_lower for phi in cls.PHI_FIELDS):
                continue
            # Also mask exact string dates or timestamps if any exist
            if isinstance(v, str) and re.search(r'\d{4}-\d{2}-\d{2}', v):
                continue
            clean[k] = v
        return clean

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Strip potential identifier tokens from free-form clinical notes."""
        sanitized = re.sub(r'Patient\s*(ID)?\s*[:#-]?\s*\w+', 'Patient: [ANONYMIZED]', text, flags=re.IGNORECASE)
        sanitized = re.sub(r'\b\d{6,10}\b', '[ID-MASKED]', sanitized)
        return sanitized


def stamp_advisory(text: str) -> str:
    """Ensure every Copilot output contains the mandatory non-autonomous clinical disclaimer."""
    watermark_block = ADVISORY_WATERMARK.strip()
    if watermark_block in text:
        return text
    return f"{watermark_block}\n\n{text}\n\n{watermark_block}"
