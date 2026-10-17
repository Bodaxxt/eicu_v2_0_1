"""Unit and integration tests for ClinicalReasoningEngine and SeverityAgent."""
import os
import pytest
from severity_agent.agent import SeverityAgent
from severity_agent.reasoning import ClinicalReasoningEngine
from severity_agent.detectors import OrganAssessment

BUNDLE_PATH = "e:/eicu_v2_0_1.sqlite3/model_artifacts/icu_guard_v4_2_agent_bundle.pkl"

def test_reasoning_engine_causality():
    engine = ClinicalReasoningEngine()
    organs = {
        "Sepsis": OrganAssessment(organ_name="Sepsis", grade=2, description="Active Sepsis"),
        "Hemodynamic": OrganAssessment(organ_name="Hemodynamic", grade=2, description="Hypotension"),
        "Renal": OrganAssessment(organ_name="Renal", grade=1, description="Oliguria"),
        "Respiratory": OrganAssessment(organ_name="Respiratory", grade=0, description="Normal"),
        "Neurological": OrganAssessment(organ_name="Neurological", grade=0, description="Normal"),
    }
    report = engine.analyze(
        probabilities={"p_mortality": 0.45, "p_deterioration": 0.65, "p_severe": 0.80},
        organ_assessments=organs,
        patterns=[],
        vitals={"heartrate_std": 18.0, "meanbp_std": 14.0, "shock_index_max": 1.25}
    )
    assert "Sepsis" in report.primary_etiology
    assert report.trajectory == "RAPID_DETERIORATION"
    assert len(report.differential_diagnosis) == 3
    assert any("Sepsis" in d.diagnosis_name for d in report.differential_diagnosis)

@pytest.mark.skipif(not os.path.exists(BUNDLE_PATH), reason="Bundle file not present")
def test_severity_agent_end_to_end():
    agent = SeverityAgent(bundle_path=BUNDLE_PATH)
    assert agent.version in ["4.2.0", "5.0.0"]
    assert "mortality" in agent.models
    assert "deterioration" in agent.models
    assert "severe" in agent.models

    # Synthetic critical patient
    crit_patient = {
        "heartrate_mean": 128.0,
        "heartrate_max": 142.0,
        "heartrate_std": 16.0,
        "meanbp_min": 48.0,       # Absolute Red Flag
        "sbp_min": 68.0,          # Absolute Red Flag
        "sao2_min": 84.0,         # Severe Hypoxemia
        "resprate_max": 36.0,
        "creatinine_max": 3.8,    # KDIGO 3
        "bun_max": 65.0,
        "gcs_min": 7.0,           # Absolute Red Flag (Coma)
        "lactate_max": 6.5,       # Severe Dysoxia
        "temperature_max": 39.4,
        "wbc_max": 18.5
    }

    assessment = agent.full_assessment(crit_patient, patient_id="TEST-CRIT-001")
    assert assessment.severity.final_tier == "CRITICAL"
    assert assessment.severity.is_critical
    assert len(assessment.severity.active_red_flags) >= 2
    assert assessment.probabilities['p_mortality'] >= 0.0

    # Ensure bilingual reports are non-empty and well-structured
    assert "ICU GUARD" in assessment.english_report
    assert "CRITICAL" in assessment.english_report
    assert "ملخص تقدير المخاطر" in assessment.arabic_report

    # Test dictionary export
    d = assessment.to_dict()
    assert d["severity_tier"] == "CRITICAL"
    assert "probabilities" in d
    assert "organs" in d
    assert "patterns" in d
