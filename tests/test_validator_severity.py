"""Unit tests for the PredictionValidator and SeverityEvaluator modules."""
import pytest
from severity_agent.detectors import OrganAssessment
from severity_agent.validator import PredictionValidator
from severity_agent.severity import SeverityEvaluator

def make_organs(max_grade: int):
    return {
        "Respiratory": OrganAssessment(organ_name="Respiratory", grade=max_grade, description="Test"),
        "Hemodynamic": OrganAssessment(organ_name="Hemodynamic", grade=0, description="Test"),
        "Renal": OrganAssessment(organ_name="Renal", grade=0, description="Test"),
        "Neurological": OrganAssessment(organ_name="Neurological", grade=0, description="Test"),
        "Sepsis": OrganAssessment(organ_name="Sepsis", grade=0, description="Test"),
    }

def test_validator_clean():
    validator = PredictionValidator()
    probs = {"p_mortality": 0.10, "p_deterioration": 0.20, "p_severe": 0.30}
    organs = make_organs(0)
    vitals = {"heartrate_mean": 75, "meanbp_mean": 80, "creatinine_max": 1.0}
    report = validator.validate(probs, organs, vitals)
    assert report.is_valid
    assert report.confidence in ["HIGH", "MODERATE"]

def test_validator_contradiction_severe_organ_low_prob():
    validator = PredictionValidator()
    # Grade 3 organ collapse with very low probability predictions
    probs = {"p_mortality": 0.02, "p_deterioration": 0.05, "p_severe": 0.10}
    organs = make_organs(3)
    report = validator.validate(probs, organs, {"vital": 1})
    assert not report.is_valid
    assert report.confidence == "LOW"
    assert len(report.contradictions_detected) > 0

def test_severity_evaluator_escalation():
    evaluator = SeverityEvaluator()
    # ML says STABLE, but patient has Grade 3 organ failure
    probs = {"p_mortality": 0.05, "p_deterioration": 0.10, "p_severe": 0.20}
    organs = make_organs(3)
    res = evaluator.evaluate(probs, organs, [], {})
    assert res.final_tier == "CRITICAL"
    assert res.escalation_occurred

def test_severity_evaluator_absolute_red_flags():
    evaluator = SeverityEvaluator()
    probs = {"p_mortality": 0.05, "p_deterioration": 0.05, "p_severe": 0.05}
    organs = make_organs(0)

    # 1. MAP < 50
    res_map = evaluator.evaluate(probs, organs, [], {"meanbp_min": 44.0})
    assert res_map.final_tier == "CRITICAL"
    assert any("MAP" in f for f in res_map.active_red_flags)

    # 2. GCS <= 8
    res_gcs = evaluator.evaluate(probs, organs, [], {"gcs_min": 5.0})
    assert res_gcs.final_tier == "CRITICAL"
    assert any("GCS" in f for f in res_gcs.active_red_flags)

    # 3. Lactate > 8
    res_lac = evaluator.evaluate(probs, organs, [], {"lactate_max": 9.5})
    assert res_lac.final_tier == "CRITICAL"
    assert any("Lactate" in f for f in res_lac.active_red_flags)
