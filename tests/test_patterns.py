"""Unit tests for the 5 clinical syndrome pattern evaluators."""
import pytest
from severity_agent.detectors import OrganAssessment
from severity_agent.patterns import (
    SepticShockPattern,
    ARDSPattern,
    AKIPattern,
    MOFPattern,
    NeuroRespiratoryPattern
)

def make_assessment(name: str, grade: int) -> OrganAssessment:
    return OrganAssessment(
        organ_name=name,
        grade=grade,
        description=f"Grade {grade} {name} failure"
    )

def test_septic_shock_pattern_detected():
    pattern = SepticShockPattern()
    organs = {
        "Sepsis": make_assessment("Sepsis", 2),
        "Hemodynamic": make_assessment("Hemodynamic", 2)
    }
    vitals = {"lactate_max": 5.2}
    res = pattern.evaluate(organs, vitals)
    assert res.detected
    assert res.confidence == "HIGH"
    assert res.urgency_tier == "IMMEDIATE"

def test_septic_shock_pattern_negative_when_lactate_normal():
    pattern = SepticShockPattern()
    organs = {
        "Sepsis": make_assessment("Sepsis", 1),
        "Hemodynamic": make_assessment("Hemodynamic", 0)
    }
    vitals = {"lactate_max": 1.2}
    res = pattern.evaluate(organs, vitals)
    assert not res.detected

def test_ards_pattern():
    pattern = ARDSPattern()
    organs = {"Respiratory": make_assessment("Respiratory", 2)}
    vitals = {"pao2_min": 58.0}
    res = pattern.evaluate(organs, vitals)
    assert res.detected
    assert res.confidence == "HIGH"

def test_aki_pattern():
    pattern = AKIPattern()
    organs = {
        "Renal": make_assessment("Renal", 2),
        "Sepsis": make_assessment("Sepsis", 1)
    }
    res = pattern.evaluate(organs, {})
    assert res.detected
    assert res.urgency_tier in ["URGENT", "MONITOR"]

def test_mof_pattern():
    pattern = MOFPattern()
    # 3 organs with grade >= 2
    organs_3 = {
        "Respiratory": make_assessment("Respiratory", 2),
        "Hemodynamic": make_assessment("Hemodynamic", 2),
        "Renal": make_assessment("Renal", 2),
        "Neurological": make_assessment("Neurological", 0)
    }
    res = pattern.evaluate(organs_3, {})
    assert res.detected
    assert res.confidence == "HIGH"
    assert res.urgency_tier == "IMMEDIATE"

def test_neuro_respiratory_pattern():
    pattern = NeuroRespiratoryPattern()
    # GCS <= 8
    organs = {
        "Neurological": make_assessment("Neurological", 3),
        "Respiratory": make_assessment("Respiratory", 1)
    }
    res = pattern.evaluate(organs, {})
    assert res.detected
    assert res.confidence == "HIGH"
    assert "Intubation" in res.clinical_recommendation or "intubation" in res.clinical_recommendation
