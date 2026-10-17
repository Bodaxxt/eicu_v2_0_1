"""Unit tests for the 5 physiological organ detectors."""
import pytest
from severity_agent.detectors import (
    RespiratoryDetector,
    HemodynamicDetector,
    RenalDetector,
    NeurologicalDetector,
    SepsisDetector
)

def test_respiratory_detector_normal():
    detector = RespiratoryDetector()
    vitals = {"sao2_min": 98.0, "resprate_mean": 16.0, "pao2_min": 90.0}
    res = detector.assess(vitals)
    assert res.grade == 0
    assert not res.is_compromised

def test_respiratory_detector_severe():
    detector = RespiratoryDetector()
    # Severe hypoxemia (SaO2 < 85%) & tachypnea
    vitals = {"sao2_min": 82.0, "resprate_max": 38.0}
    res = detector.assess(vitals)
    assert res.grade == 3
    assert res.is_critical
    assert any("Severe hypoxemia" in ev for ev in res.clinical_evidence)

def test_respiratory_detector_bradypnea():
    detector = RespiratoryDetector()
    # Bradypnea / exhaustion
    vitals = {"sao2_min": 92.0, "resprate_max": 6.0}
    res = detector.assess(vitals)
    assert res.grade == 3

def test_hemodynamic_detector_normal():
    detector = HemodynamicDetector()
    vitals = {"meanbp_min": 85.0, "sbp_min": 120.0, "heartrate_mean": 75.0, "shock_index": 0.62}
    res = detector.assess(vitals)
    assert res.grade == 0
    assert not res.is_compromised

def test_hemodynamic_detector_shock():
    detector = HemodynamicDetector()
    # Profound hypotension & high shock index
    vitals = {"meanbp_min": 45.0, "sbp_min": 65.0, "heartrate_max": 125.0, "shock_index": 1.4}
    res = detector.assess(vitals)
    assert res.grade == 3
    assert res.is_critical

def test_renal_detector_kdigo_stages():
    detector = RenalDetector()
    # Stage 1
    res1 = detector.assess({"creatinine_max": 1.5, "bun_max": 30.0})
    assert res1.grade == 1
    # Stage 2
    res2 = detector.assess({"creatinine_max": 2.5, "bun_max": 50.0})
    assert res2.grade == 2
    # Stage 3
    res3 = detector.assess({"creatinine_max": 4.2, "bun_max": 85.0})
    assert res3.grade == 3
    assert res3.is_critical

def test_neurological_detector_gcs():
    detector = NeurologicalDetector()
    # Intact
    assert detector.assess({"gcs_min": 15}).grade == 0
    # Mild
    assert detector.assess({"gcs_min": 13}).grade == 1
    # Moderate
    assert detector.assess({"gcs_min": 10}).grade == 2
    # Severe Coma / Loss of airway
    res_severe = detector.assess({"gcs_min": 6})
    assert res_severe.grade == 3
    assert res_severe.is_critical

def test_sepsis_detector_sirs_and_shock():
    detector = SepsisDetector()
    # SIRS negative
    assert detector.assess({"temperature_max": 37.0, "heartrate_mean": 70, "wbc_max": 8.0}).grade == 0
    # SIRS positive (Fever + Tachycardia)
    res_sirs = detector.assess({"temperature_max": 39.2, "heartrate_mean": 110.0, "wbc_max": 14.5})
    assert res_sirs.grade >= 1
    # Septic hypoperfusion with high lactate
    res_septic = detector.assess({"temperature_max": 39.0, "heartrate_mean": 115.0, "lactate_max": 4.8})
    assert res_septic.grade == 3
