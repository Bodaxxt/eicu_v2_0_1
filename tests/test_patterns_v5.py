"""Unit tests for all 16 clinical syndrome patterns in ICU Guard v5.0."""
import pytest
from severity_agent.detectors import OrganAssessment
from severity_agent.patterns import (
    SepticShockPattern,
    ARDSPattern,
    AKIPattern,
    MOFPattern,
    NeuroRespiratoryPattern,
    CardiogenicShockPattern,
    HemorrhagicShockPattern,
    DICPattern,
    DeliriumPattern,
    RefractoryShockPattern,
    Type1RespiratoryFailurePattern,
    Type2RespiratoryFailurePattern,
    HepatorenalSyndromePattern,
    PostoperativeDeteriorationPattern,
    SevereAcidemiaPattern,
    HyperosmolarCrisisPattern
)

def _mock_organs(**grades):
    organs = {}
    for name, g in grades.items():
        organs[name] = OrganAssessment(
            organ_name=name,
            grade=g,
            description=f"{name} Grade {g}"
        )
    return organs

# 1. Septic Shock
def test_septic_shock():
    pat = SepticShockPattern()
    orgs = _mock_organs(Sepsis=2, Hemodynamic=2)
    m = pat.evaluate(orgs, {"lactate_max": 5.2})
    assert m.detected
    assert m.confidence == "HIGH"
    assert m.urgency_tier == "IMMEDIATE"

# 2. ARDS
def test_ards():
    pat = ARDSPattern()
    orgs = _mock_organs(Respiratory=2)
    m = pat.evaluate(orgs, {"pao2_min": 55.0, "sao2_min": 85.0})
    assert m.detected
    assert m.confidence == "HIGH"

# 3. AKI
def test_aki():
    pat = AKIPattern()
    orgs = _mock_organs(Renal=2)
    m = pat.evaluate(orgs, {"creatinine_max": 2.5})
    assert m.detected

# 4. MOF
def test_mof():
    pat = MOFPattern()
    orgs = _mock_organs(Respiratory=2, Renal=2, Hemodynamic=2)
    m = pat.evaluate(orgs, {})
    assert m.detected
    assert m.urgency_tier == "IMMEDIATE"

# 5. Neuro-Respiratory
def test_neuro_resp():
    pat = NeuroRespiratoryPattern()
    orgs = _mock_organs(Neurological=3, Respiratory=1)
    m = pat.evaluate(orgs, {})
    assert m.detected
    assert m.urgency_tier == "IMMEDIATE"

# 6. Cardiogenic Shock
def test_cardiogenic_shock():
    pat = CardiogenicShockPattern()
    orgs = _mock_organs(Hemodynamic=2, Respiratory=1)
    m = pat.evaluate(orgs, {"meanbp_min": 60.0, "sbp_min": 85.0, "dbp_min": 60.0, "shock_index_max": 1.1})
    assert m.detected
    assert "Cardiogenic" in m.pattern_name
    assert "inotropic" in m.clinical_recommendation.lower()

# 7. Hemorrhagic Shock
def test_hemorrhagic_shock():
    pat = HemorrhagicShockPattern()
    orgs = _mock_organs(Hemodynamic=2, Hematologic=2)
    m = pat.evaluate(orgs, {"hemoglobin_min": 6.8, "meanbp_min": 58.0, "heartrate_max": 128.0})
    assert m.detected
    assert m.confidence == "HIGH"
    assert "Massive Transfusion" in m.clinical_recommendation

# 8. DIC
def test_dic():
    pat = DICPattern()
    orgs = _mock_organs(Coagulation=2, Sepsis=2)
    m = pat.evaluate(orgs, {"platelets_min": 65.0, "inr_max": 2.1, "ptt_max": 58.0})
    assert m.detected
    assert m.urgency_tier == "IMMEDIATE"

# 9. Delirium
def test_delirium():
    pat = DeliriumPattern()
    orgs = _mock_organs(Neurological=1)
    m = pat.evaluate(orgs, {"gcs_min": 12.0})
    assert m.detected
    assert m.urgency_tier == "MONITOR"

# 10. Refractory Shock
def test_refractory_shock():
    pat = RefractoryShockPattern()
    orgs = _mock_organs(Hemodynamic=2)
    m = pat.evaluate(orgs, {"vasopressor_6h": 1.0, "lactate_max": 5.8, "meanbp_min": 62.0})
    assert m.detected
    assert m.confidence == "HIGH"
    assert "vasopressin" in m.clinical_recommendation.lower()

# 11. Type 1 Respiratory Failure
def test_type1_resp_failure():
    pat = Type1RespiratoryFailurePattern()
    orgs = _mock_organs(Respiratory=2)
    m = pat.evaluate(orgs, {"pao2_min": 54.0, "sao2_min": 86.0, "paco2_max": 38.0})
    assert m.detected
    assert "Hypoxemic" in m.pattern_name

# 12. Type 2 Respiratory Failure
def test_type2_resp_failure():
    pat = Type2RespiratoryFailurePattern()
    orgs = _mock_organs(Respiratory=2)
    m = pat.evaluate(orgs, {"paco2_max": 62.0, "ph_min": 7.26})
    assert m.detected
    assert m.confidence == "HIGH"
    assert "Hypercapnic" in m.pattern_name

# 13. Hepatorenal Syndrome
def test_hepatorenal_syndrome():
    pat = HepatorenalSyndromePattern()
    orgs = _mock_organs(Hepatic=2, Renal=2)
    m = pat.evaluate(orgs, {})
    assert m.detected
    assert "HRS-AKI" in m.pattern_name
    assert "albumin" in m.clinical_recommendation.lower()

# 14. Postoperative Deterioration
def test_postoperative_deterioration():
    pat = PostoperativeDeteriorationPattern()
    orgs = _mock_organs(Hemodynamic=2)
    m = pat.evaluate(orgs, {"admissiontype_PACU": 1, "meanbp_min": 58.0})
    assert m.detected
    assert "Post-Operative" in m.pattern_name

# 15. Severe Acidemia
def test_severe_acidemia():
    pat = SevereAcidemiaPattern()
    orgs = _mock_organs(Metabolic=3)
    m = pat.evaluate(orgs, {"ph_min": 7.12, "lactate_max": 6.8})
    assert m.detected
    assert m.urgency_tier == "IMMEDIATE"

# 16. Hyperosmolar Crisis / DKA
def test_hyperosmolar_crisis():
    pat = HyperosmolarCrisisPattern()
    orgs = _mock_organs(Endocrine=2)
    m = pat.evaluate(orgs, {"glucose_max": 380.0, "ph_min": 7.24, "sodium_mean": 148.0})
    assert m.detected
    assert m.confidence == "HIGH"
    assert "insulin" in m.clinical_recommendation.lower()

# Negative & Edge Tests for Differential Discernment
def test_cardiogenic_shock_negative_when_hemodynamics_normal():
    pat = CardiogenicShockPattern()
    orgs = _mock_organs(Hemodynamic=0)
    m = pat.evaluate(orgs, {"troponin_max": 2.5, "meanbp_min": 85.0})
    assert not m.detected

def test_hemorrhagic_shock_negative_when_hb_normal():
    pat = HemorrhagicShockPattern()
    orgs = _mock_organs(Hemodynamic=2)
    m = pat.evaluate(orgs, {"hemoglobin_min": 14.0, "meanbp_min": 55.0})
    assert not m.detected

def test_dic_negative_when_platelets_and_inr_normal():
    pat = DICPattern()
    orgs = _mock_organs(Coagulation=0)
    m = pat.evaluate(orgs, {"platelets_min": 250.0, "inr_max": 1.0})
    assert not m.detected

def test_delirium_negative_when_gcs_normal():
    pat = DeliriumPattern()
    orgs = _mock_organs(Neurological=0)
    m = pat.evaluate(orgs, {"gcs_min": 15.0})
    assert not m.detected

def test_refractory_shock_negative_when_lactate_normal():
    pat = RefractoryShockPattern()
    orgs = _mock_organs(Hemodynamic=2)
    m = pat.evaluate(orgs, {"lactate_max": 1.1, "meanbp_min": 55.0})
    assert not m.detected

def test_hepatorenal_negative_when_liver_normal():
    pat = HepatorenalSyndromePattern()
    orgs = _mock_organs(Renal=2, Hepatic=0)
    m = pat.evaluate(orgs, {"creatinine_max": 2.5, "bilirubin_max": 0.6})
    assert not m.detected

def test_all_patterns_empty_inputs():
    from severity_agent.agent import SeverityAgent
    # All 16 patterns evaluated against completely empty inputs
    patterns = [
        SepticShockPattern(), ARDSPattern(), AKIPattern(), MOFPattern(),
        NeuroRespiratoryPattern(), CardiogenicShockPattern(), HemorrhagicShockPattern(),
        DICPattern(), DeliriumPattern(), RefractoryShockPattern(),
        Type1RespiratoryFailurePattern(), Type2RespiratoryFailurePattern(),
        HepatorenalSyndromePattern(), PostoperativeDeteriorationPattern(),
        SevereAcidemiaPattern(), HyperosmolarCrisisPattern()
    ]
    for pat in patterns:
        res = pat.evaluate({}, {})
        assert not res.detected
        assert res.confidence == "NONE"
        assert res.urgency_tier == "ROUTINE"

def test_all_patterns_healthy_patient():
    patterns = [
        SepticShockPattern(), ARDSPattern(), AKIPattern(), MOFPattern(),
        NeuroRespiratoryPattern(), CardiogenicShockPattern(), HemorrhagicShockPattern(),
        DICPattern(), DeliriumPattern(), RefractoryShockPattern(),
        Type1RespiratoryFailurePattern(), Type2RespiratoryFailurePattern(),
        HepatorenalSyndromePattern(), PostoperativeDeteriorationPattern(),
        SevereAcidemiaPattern(), HyperosmolarCrisisPattern()
    ]
    healthy_organs = _mock_organs(
        Respiratory=0, Hemodynamic=0, Renal=0, Neurological=0,
        Sepsis=0, Hepatic=0, Coagulation=0, Metabolic=0,
        Endocrine=0, Hematologic=0, Nutritional=0
    )
    healthy_vitals = {
        "heartrate_mean": 75.0, "meanbp_min": 85.0, "resprate_max": 16.0,
        "sao2_min": 98.0, "creatinine_max": 0.8, "gcs_min": 15.0,
        "temperature_max": 37.0, "wbc_max": 7.0, "lactate_max": 1.0,
        "bilirubin_max": 0.6, "platelets_min": 250.0, "ph_min": 7.40,
        "glucose_max": 105.0, "hemoglobin_min": 14.5
    }
    for pat in patterns:
        res = pat.evaluate(healthy_organs, healthy_vitals)
        assert not res.detected
