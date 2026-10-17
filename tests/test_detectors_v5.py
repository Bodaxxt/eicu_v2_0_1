"""Unit tests for all 11 organ system detectors in ICU Guard v5.0."""
import pytest
from severity_agent.detectors import (
    RespiratoryDetector,
    HemodynamicDetector,
    RenalDetector,
    NeurologicalDetector,
    SepsisDetector,
    HepaticDetector,
    CoagulationDetector,
    MetabolicDetector,
    EndocrineDetector,
    HematologicDetector,
    NutritionalDetector
)

# 1. Respiratory Detector
def test_resp_normal():
    d = RespiratoryDetector()
    res = d.assess({"sao2_min": 98.0, "pao2_min": 95.0, "resprate_max": 16.0})
    assert res.grade == 0
    assert not res.is_compromised

def test_resp_mild():
    d = RespiratoryDetector()
    res = d.assess({"sao2_min": 93.0, "resprate_max": 24.0})
    assert res.grade == 1
    assert res.is_compromised

def test_resp_severe():
    d = RespiratoryDetector()
    res = d.assess({"sao2_min": 82.0, "pao2_min": 48.0, "resprate_max": 38.0})
    assert res.grade == 3
    assert res.is_critical

# 2. Hemodynamic Detector
def test_hemo_normal():
    d = HemodynamicDetector()
    res = d.assess({"meanbp_min": 75.0, "sbp_min": 115.0, "heartrate_max": 78.0})
    assert res.grade == 0

def test_hemo_shock():
    d = HemodynamicDetector()
    res = d.assess({"meanbp_min": 48.0, "sbp_min": 68.0, "heartrate_max": 135.0})
    assert res.grade == 3
    assert res.is_critical

# 3. Renal Detector
def test_renal_kdigo_stages():
    d = RenalDetector()
    assert d.assess({"creatinine_max": 0.9}).grade == 0
    assert d.assess({"creatinine_max": 1.5}).grade == 1
    assert d.assess({"creatinine_max": 2.4}).grade == 2
    assert d.assess({"creatinine_max": 4.1}).grade == 3

# 4. Neurological Detector
def test_neuro_gcs_spectrum():
    d = NeurologicalDetector()
    assert d.assess({"gcs_min": 15.0}).grade == 0
    assert d.assess({"gcs_min": 13.0}).grade == 1
    assert d.assess({"gcs_min": 10.0}).grade == 2
    assert d.assess({"gcs_min": 6.0}).grade == 3

# 5. Sepsis Detector
def test_sepsis_sirs_grades():
    d = SepsisDetector()
    # Normal
    assert d.assess({"temperature_max": 37.0, "heartrate_max": 75.0, "wbc_max": 7.0}).grade == 0
    # SIRS only (2 criteria: temp and HR)
    assert d.assess({"temperature_max": 39.2, "heartrate_max": 110.0, "resprate_max": 18.0, "wbc_max": 8.0}).grade == 1
    # SIRS high burden (>= 3 criteria)
    assert d.assess({"temperature_max": 39.2, "heartrate_max": 110.0, "resprate_max": 24.0, "wbc_max": 15.0}).grade == 2
    # Sepsis with Dysoxia
    assert d.assess({"temperature_max": 39.2, "heartrate_max": 110.0, "lactate_max": 6.5}).grade == 3

# 6. Hepatic Detector
def test_hepatic_normal():
    d = HepaticDetector()
    res = d.assess({"bilirubin_max": 0.8, "inr_max": 1.0})
    assert res.grade == 0
    assert "Normal Hepatic" in res.description

def test_hepatic_grade2():
    d = HepaticDetector()
    res = d.assess({"bilirubin_max": 2.5, "inr_max": 1.8})
    assert res.grade == 2
    assert res.is_critical

def test_hepatic_grade3():
    d = HepaticDetector()
    res = d.assess({"bilirubin_max": 7.5, "inr_max": 2.8})
    assert res.grade == 3
    assert "SOFA Liver" in res.clinical_evidence[0]
    assert len(res.suggested_action) > 0

# 7. Coagulation Detector
def test_coag_normal():
    d = CoagulationDetector()
    res = d.assess({"platelets_min": 220.0, "inr_max": 1.1, "ptt_max": 30.0})
    assert res.grade == 0

def test_coag_moderate():
    d = CoagulationDetector()
    res = d.assess({"platelets_min": 85.0, "inr_max": 1.9})
    assert res.grade == 2

def test_coag_severe():
    d = CoagulationDetector()
    res = d.assess({"platelets_min": 35.0, "inr_max": 2.8, "ptt_max": 78.0})
    assert res.grade == 3
    assert res.is_critical

# 8. Metabolic Detector
def test_metab_normal():
    d = MetabolicDetector()
    res = d.assess({"ph_min": 7.40, "lactate_max": 1.1})
    assert res.grade == 0

def test_metab_severe_acidemia():
    d = MetabolicDetector()
    res = d.assess({"ph_min": 7.12, "lactate_max": 6.5})
    assert res.grade == 3
    assert res.is_critical

# 9. Endocrine Detector
def test_endocrine_normal():
    d = EndocrineDetector()
    res = d.assess({"glucose_mean": 110.0})
    assert res.grade == 0

def test_endocrine_hypoglycemia_severe():
    d = EndocrineDetector()
    res = d.assess({"glucose_min": 35.0})
    assert res.grade == 3
    assert "neuroglycopenia" in res.clinical_evidence[0].lower()

def test_endocrine_hyperglycemia_dka():
    d = EndocrineDetector()
    res = d.assess({"glucose_max": 280.0})
    assert res.grade == 2

def test_endocrine_hyperglycemia_severe():
    d = EndocrineDetector()
    res = d.assess({"glucose_max": 450.0})
    assert res.grade == 3

# 10. Hematologic Detector
def test_hematologic_normal():
    d = HematologicDetector()
    res = d.assess({"hemoglobin_min": 13.5})
    assert res.grade == 0

def test_hematologic_moderate():
    d = HematologicDetector()
    res = d.assess({"hemoglobin_min": 7.8})
    assert res.grade == 2

def test_hematologic_severe_transfusion_trigger():
    d = HematologicDetector()
    res = d.assess({"hemoglobin_min": 6.5})
    assert res.grade == 3
    assert "transfusion" in res.description.lower()

# 11. Nutritional Detector
def test_nutritional_normal():
    d = NutritionalDetector()
    res = d.assess({"bmi": 24.5, "albumin_min": 3.8})
    assert res.grade == 0

def test_nutritional_cachexia():
    d = NutritionalDetector()
    res = d.assess({"bmi": 15.2, "albumin_min": 1.9})
    assert res.grade == 3
    assert "cachexia" in res.clinical_evidence[0].lower()

def test_nutritional_morbid_obesity():
    d = NutritionalDetector()
    res = d.assess({"bmi": 42.0})
    assert res.grade == 2

# Robustness & Missing Value Handling for all 11 detectors
def test_all_detectors_empty_vitals():
    detectors = [
        RespiratoryDetector(), HemodynamicDetector(), RenalDetector(),
        NeurologicalDetector(), SepsisDetector(), HepaticDetector(),
        CoagulationDetector(), MetabolicDetector(), EndocrineDetector(),
        HematologicDetector(), NutritionalDetector()
    ]
    for d in detectors:
        res = d.assess({})
        assert res.grade == 0
        assert not res.is_critical
        assert isinstance(res.clinical_evidence, list)

def test_all_detectors_nan_vitals():
    import numpy as np
    nan_dict = {
        "resprate_max": np.nan, "sao2_min": np.nan, "pao2_min": np.nan,
        "meanbp_min": np.nan, "sbp_min": np.nan, "creatinine_max": np.nan,
        "gcs_min": np.nan, "lactate_max": np.nan, "temperature_max": np.nan,
        "bilirubin_max": np.nan, "platelets_min": np.nan, "ph_min": np.nan,
        "glucose_max": np.nan, "hemoglobin_min": np.nan, "bmi": np.nan
    }
    detectors = [
        RespiratoryDetector(), HemodynamicDetector(), RenalDetector(),
        NeurologicalDetector(), SepsisDetector(), HepaticDetector(),
        CoagulationDetector(), MetabolicDetector(), EndocrineDetector(),
        HematologicDetector(), NutritionalDetector()
    ]
    for d in detectors:
        res = d.assess(nan_dict)
        assert res.grade == 0
        assert not res.is_critical

def test_respiratory_bradypnea_apnea():
    d = RespiratoryDetector()
    res = d.assess({"resprate_min": 6.0})
    assert res.grade == 3
    assert res.is_critical

def test_hemodynamic_hypertensive_crisis():
    d = HemodynamicDetector()
    res = d.assess({"sbp_max": 205.0})
    assert res.grade == 2

def test_metabolic_respiratory_alkalemia():
    d = MetabolicDetector()
    res = d.assess({"ph_max": 7.58})
    assert res.grade == 2

def test_endocrine_severe_hyperglycemia_hhns():
    d = EndocrineDetector()
    res = d.assess({"glucose_max": 650.0})
    assert res.grade == 3
    assert res.is_critical
