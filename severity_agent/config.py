"""
ICU Guard v4.2 — Severity Agent Configuration & Clinical Thresholds
===================================================================
All clinical thresholds and score cutoff definitions are isolated here
to allow multidisciplinary medical review (Intensivists, Critical Care Nurses).

Clinical Guideline References:
- Surviving Sepsis Campaign (SSC 2021)
- KDIGO Clinical Practice Guideline for Acute Kidney Injury (2012)
- Berlin Definition for Acute Respiratory Distress Syndrome (ARDS 2012)
- ACCP/SCCM Consensus Conference Committee for SIRS Criteria (1992/2001)
"""

from typing import Dict, Any, List

# =============================================================================
# 1. ORGAN DETECTOR THRESHOLDS (Grades 0 to 3)
# =============================================================================

RESPIRATORY_CONFIG: Dict[str, Any] = {
    # Berlin ARDS definitions & Hypoxemia cutoffs
    "sao2_grade1": 95.0,        # SaO2 < 95% indicates mild impairment
    "sao2_grade2": 90.0,        # SaO2 < 90% moderate hypoxemia
    "sao2_grade3": 85.0,        # SaO2 < 85% severe hypoxemic respiratory failure
    "pao2_grade1": 80.0,        # PaO2 < 80 mmHg (mild)
    "pao2_grade2": 60.0,        # PaO2 < 60 mmHg (moderate)
    "pao2_grade3": 50.0,        # PaO2 < 50 mmHg (severe / impending arrest)
    "rr_high_grade1": 22.0,     # Tachypnea > 22
    "rr_high_grade2": 28.0,     # Tachypnea > 28
    "rr_high_grade3": 35.0,     # Severe tachypnea > 35
    "rr_low_grade3": 8.0,       # Bradypnea / respiratory exhaustion < 8
    "o2_reserve_low": 20.0,     # Severe O2 reserve exhaustion
}

HEMODYNAMIC_CONFIG: Dict[str, Any] = {
    # Perfusion pressure & shock index thresholds
    "map_grade1": 70.0,         # MAP < 70 mmHg (borderline perfusion)
    "map_grade2": 65.0,         # MAP < 65 mmHg (SSC target failure)
    "map_grade3": 50.0,         # MAP < 50 mmHg (profound collapse)
    "sbp_grade1": 90.0,         # SBP < 90 mmHg
    "sbp_grade2": 80.0,         # SBP < 80 mmHg
    "sbp_grade3": 70.0,         # SBP < 70 mmHg (refractory hypotension)
    "hr_high_grade1": 100.0,    # Tachycardia > 100 bpm
    "hr_high_grade2": 120.0,    # Marked tachycardia > 120 bpm
    "hr_high_grade3": 140.0,    # Extreme tachycardia > 140 bpm
    "hr_low_grade3": 45.0,      # Severe bradycardia < 45 bpm
    "shock_index_grade1": 0.7,  # Shock Index (HR/SBP) > 0.7 (compensated)
    "shock_index_grade2": 0.9,  # Shock Index > 0.9 (uncompensated)
    "shock_index_grade3": 1.3,  # Shock Index > 1.3 (severe shock state)
}

RENAL_CONFIG: Dict[str, Any] = {
    # KDIGO 2012 AKI staging criteria (approx based on static lab availability)
    "cr_grade1": 1.3,           # Serum Creatinine > 1.3 mg/dL (KDIGO Stage 1 equivalent)
    "cr_grade2": 2.0,           # Serum Creatinine > 2.0 mg/dL (KDIGO Stage 2 equivalent)
    "cr_grade3": 3.5,           # Serum Creatinine > 3.5 mg/dL (KDIGO Stage 3 / renal failure)
    "bun_grade1": 25.0,         # BUN > 25 mg/dL
    "bun_grade2": 45.0,         # BUN > 45 mg/dL
    "bun_grade3": 70.0,         # BUN > 70 mg/dL (severe uremic burden)
    "urine_rate_grade1": 0.5,   # Urine output < 0.5 ml/kg/h
    "urine_rate_grade2": 0.3,   # Oliguria < 0.3 ml/kg/h
    "urine_rate_grade3": 0.1,   # Anuria / extreme oliguria < 0.1 ml/kg/h
}

NEUROLOGICAL_CONFIG: Dict[str, Any] = {
    # Glasgow Coma Scale (GCS) severity spectrum
    "gcs_grade1": 14.0,         # GCS 13-14: Mild encephalopathy
    "gcs_grade2": 12.0,         # GCS 9-12: Moderate coma / obtundation
    "gcs_grade3": 8.0,          # GCS <= 8: Severe coma / loss of protective airway reflexes
}

SEPSIS_CONFIG: Dict[str, Any] = {
    # SIRS + SSC 2021 septic shock indicators
    "temp_high": 38.0,          # Hyperthermia > 38.0 °C
    "temp_low": 36.0,           # Hypothermia < 36.0 °C (ominous sign in sepsis)
    "hr_sirs": 90.0,            # Heart rate > 90 bpm
    "rr_sirs": 20.0,            # Respiratory rate > 20 bpm
    "wbc_high": 12.0,           # Leukocytosis > 12.0 x 10^9 / L
    "wbc_low": 4.0,             # Leukopenia < 4.0 x 10^9 / L
    "lactate_grade1": 2.0,      # Hyperlactatemia > 2.0 mmol/L (tissue hypoperfusion)
    "lactate_grade2": 4.0,      # Elevated lactate > 4.0 mmol/L (severe cellular distress)
    "lactate_grade3": 6.0,      # Critical lactate > 6.0 mmol/L (high risk of mortality)
}

# ----------------- v5.0 NEW ORGAN DETECTORS -----------------

HEPATIC_CONFIG: Dict[str, Any] = {
    # SOFA Liver component & Child-Pugh / EASL guidelines
    "bili_grade1": 1.2,         # Bilirubin > 1.2 mg/dL (20 umol/L) - Mild hyperbilirubinemia
    "bili_grade2": 2.0,         # Bilirubin > 2.0 mg/dL (33 umol/L) - SOFA Grade 2 liver failure
    "bili_grade3": 6.0,         # Bilirubin > 6.0 mg/dL (102 umol/L) - Severe hepatic dysfunction / SOFA Grade 3-4
    "inr_grade1": 1.3,          # Impaired hepatic synthetic function
    "inr_grade2": 1.7,          # Moderate coagulopathy of liver disease
    "inr_grade3": 2.5,          # Acute hepatic decompensation / fulminant liver failure
}

COAGULATION_CONFIG: Dict[str, Any] = {
    # ISTH Overt DIC Scoring Guidelines & SOFA Coagulation
    "plt_grade1": 150.0,        # Platelets < 150 x 10^9/L - Mild thrombocytopenia
    "plt_grade2": 100.0,        # Platelets < 100 x 10^9/L - SOFA Grade 2 / ISTH threshold
    "plt_grade3": 50.0,         # Platelets < 50 x 10^9/L - Severe bleeding hazard / SOFA Grade 3
    "inr_grade1": 1.4,          # INR prolongation > 1.4
    "inr_grade2": 1.8,          # INR > 1.8 (coagulopathic risk)
    "inr_grade3": 2.5,          # INR > 2.5 (severe coagulopathy)
    "ptt_grade1": 38.0,         # PTT > 38 s (mildly prolonged)
    "ptt_grade2": 50.0,         # PTT > 50 s (moderate prolongation)
    "ptt_grade3": 70.0,         # PTT > 70 s (critical bleeding risk)
}

METABOLIC_CONFIG: Dict[str, Any] = {
    # Arterial Blood Gas & Stewart Acid-Base Guidelines
    "ph_low_grade1": 7.35,      # Mild acidemia
    "ph_low_grade2": 7.25,      # Moderate acidemia
    "ph_low_grade3": 7.15,      # Severe acidemia / impending hemodynamic unresponsiveness
    "ph_high_grade1": 7.45,     # Mild alkalemia
    "ph_high_grade2": 7.55,     # Severe alkalemia (arrhythmogenic risk)
    "anion_gap_grade1": 12.0,   # Borderline anion gap
    "anion_gap_grade2": 16.0,   # High anion gap metabolic acidosis (HAGMA)
    "anion_gap_grade3": 22.0,   # Severe HAGMA (lactic / ketoacidosis / toxic)
    "lactate_grade1": 2.0,
    "lactate_grade2": 4.0,
    "lactate_grade3": 6.0,
}

ENDOCRINE_CONFIG: Dict[str, Any] = {
    # ADA Standards of Medical Care in Hospitalized Patients & Surviving Sepsis
    "glucose_hypo_grade1": 70.0, # Mild hypoglycemia (autonomic trigger)
    "glucose_hypo_grade2": 54.0, # Clinically significant hypoglycemia (neuroglycopenic risk)
    "glucose_hypo_grade3": 40.0, # Severe hypoglycemia / coma / seizure hazard
    "glucose_hyper_grade1": 180.0, # Target failure / stress hyperglycemia
    "glucose_hyper_grade2": 250.0, # DKA / Hyperosmolar threshold
    "glucose_hyper_grade3": 400.0, # Severe hyperosmolar hyperglycemia (HHS danger)
}

HEMATOLOGIC_CONFIG: Dict[str, Any] = {
    # AABB Clinical Practice Guidelines & Transfusion Thresholds
    "hgb_grade1": 10.0,         # Mild anemia
    "hgb_grade2": 8.0,          # Moderate anemia / restrictive transfusion threshold consideration
    "hgb_grade3": 7.0,          # Severe anemia / absolute transfusion trigger in critical illness
}

NUTRITIONAL_CONFIG: Dict[str, Any] = {
    # ASPEN / ESPEN Critical Care Nutrition Guidelines
    "bmi_underweight_grade1": 18.5, # Malnutrition risk
    "bmi_underweight_grade2": 16.0, # Severe cachexia / wasting syndrome
    "bmi_obese_grade1": 35.0,       # Class II obesity
    "bmi_obese_grade2": 40.0,       # Class III morbid obesity (altered pharmacokinetics & ventilatory mechanics)
    "albumin_grade1": 3.0,          # Hypoalbuminemia
    "albumin_grade2": 2.2,          # Severe hypoalbuminemia / oncotic pressure loss
}

# =============================================================================
# 2. ABSOLUTE RED FLAGS (Safety Override -> Immediate CRITICAL)
# =============================================================================

ABSOLUTE_RED_FLAGS: Dict[str, Any] = {
    "gcs_min": 8.0,             # GCS <= 8 (Airway loss)
    "meanbp_min": 50.0,         # MAP < 50 mmHg (Cerebral/coronary hypoperfusion)
    "sbp_min": 70.0,            # SBP < 70 mmHg (Cardiovascular collapse)
    "sao2_min": 50.0,           # SaO2 < 50% (Extreme anoxia)
    "pao2_min": 50.0,           # PaO2 < 50 mmHg (Critical respiratory failure)
    "lactate_max": 8.0,         # Lactate > 8.0 mmol/L (Severe lactic acidosis)
    "ph_min": 7.10,             # pH < 7.10 (Severe acidemia)
    "glucose_min": 40.0,        # Severe neuroglycopenia (< 40 mg/dL)
    "platelets_min": 20.0,      # Extreme spontaneous hemorrhage risk (< 20 x 10^9/L)
    "potassium_max": 6.5,       # Hyperkalemia cardiac arrest risk (> 6.5 mmol/L)
    "potassium_min": 2.5,       # Severe hypokalemia arrhythmia risk (< 2.5 mmol/L)
}

# =============================================================================
# 3. CLINICAL SYNDROME & PATTERN CONFIGURATION (16 Patterns)
# =============================================================================

PATTERN_CONFIG: Dict[str, Any] = {
    # Original 5 Patterns
    "septic_shock": {
        "lactate_cutoff": 4.0,      # Lactate > 4.0 mmol/L
        "min_hemo_grade": 1,        # Requires hemodynamic instability
        "min_sepsis_grade": 2,      # Requires evident infection/SIRS
    },
    "ards": {
        "min_resp_grade": 2,        # Moderate to severe respiratory failure
        "pao2_cutoff": 60.0,        # Severe hypoxemia
    },
    "aki": {
        "min_renal_grade": 2,       # Grade >= 2 renal injury
    },
    "mof": {
        "min_affected_organs": 3,   # >= 3 organ systems
        "min_organ_grade": 2,       # each with grade >= 2
    },
    "neuro_respiratory": {
        "min_neuro_grade": 2,       # GCS <= 12
        "min_resp_grade": 1,        # Respiratory compromise
    },
    # v5.0 11 New Patterns
    "cardiogenic_shock": {
        "map_cutoff": 65.0,
        "shock_index_cutoff": 0.9,
        "pulse_pressure_cutoff": 30.0, # Narrow pulse pressure
        "min_resp_grade": 1,           # Hydrostatic pulmonary congestion
    },
    "hemorrhagic_shock": {
        "hgb_cutoff": 8.0,
        "map_cutoff": 65.0,
        "hr_cutoff": 100.0,
        "shock_index_cutoff": 0.9,
    },
    "dic": {
        "plt_cutoff": 100.0,
        "inr_cutoff": 1.5,
        "ptt_cutoff": 45.0,
    },
    "delirium": {
        "gcs_max": 14.0,
        "gcs_min": 9.0,
        "min_neuro_grade": 1,
    },
    "refractory_shock": {
        "map_cutoff": 65.0,
        "lactate_cutoff": 4.0,
        "vasopressor_required": True,
    },
    "type1_resp_failure": {
        "pao2_cutoff": 60.0,
        "sao2_cutoff": 90.0,
        "paco2_max": 45.0,          # Normocapnic or hypocapnic hypoxemic failure
    },
    "type2_resp_failure": {
        "paco2_cutoff": 50.0,       # Hypercapnic ventilatory pump failure
        "ph_cutoff": 7.35,          # With respiratory acidosis
    },
    "hepatorenal_syndrome": {
        "min_hepatic_grade": 2,
        "min_renal_grade": 2,
        "exclude_shock": False,
    },
    "postoperative_deterioration": {
        "min_hemo_or_resp_grade": 1,
    },
    "severe_acidemia": {
        "ph_cutoff": 7.20,
    },
    "hyperosmolar_crisis": {
        "glucose_cutoff": 250.0,
    }
}

# =============================================================================
# 4. UNCERTAINTY QUANTIFICATION CONFIGURATION
# =============================================================================

UNCERTAINTY_CONFIG: Dict[str, Any] = {
    "bootstrap_samples": 100,
    "confidence_level": 0.95,
    "conformal_alpha": 0.10,     # 90% prediction intervals
    "ood_mahalanobis_threshold": 3.0,
    "high_uncertainty_threshold": 0.40,
    "moderate_uncertainty_threshold": 0.20,
}

# =============================================================================
# 5. TRIAGE & SEVERITY LEVEL MAPPINGS
# =============================================================================

SEVERITY_LEVELS: List[str] = ["STABLE", "MODERATE", "HIGH", "CRITICAL"]

SEVERITY_ORDER: Dict[str, int] = {
    "STABLE": 0,
    "MODERATE": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}

ML_PROBABILITY_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "mortality": {
        "critical": 0.70,
        "high": 0.40,
        "moderate": 0.20,
    },
    "deterioration": {
        "critical": 0.85,
        "high": 0.50,
        "moderate": 0.30,
    },
    "severe": {
        "moderate": 0.50,
    }
}
