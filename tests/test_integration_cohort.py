"""Integration tests on real eICU cohort patients and clinical archetypes."""
import os
import pytest
import pandas as pd
from severity_agent.agent import SeverityAgent

COHORT_PATH = "e:/eicu_v2_0_1.sqlite3/multilabel_cohort.csv"
BUNDLE_PATH = "e:/eicu_v2_0_1.sqlite3/model_artifacts/icu_guard_v4_2_agent_bundle.pkl"

@pytest.fixture(scope="module")
def agent():
    if not os.path.exists(BUNDLE_PATH):
        pytest.skip("Bundle not present")
    return SeverityAgent(bundle_path=BUNDLE_PATH)

@pytest.fixture(scope="module")
def cohort_df():
    if not os.path.exists(COHORT_PATH):
        pytest.skip("Cohort CSV not present")
    return pd.read_csv(COHORT_PATH)

def test_integration_cohort_100_patients(agent, cohort_df):
    """Assess 100 consecutive real ICU patients to ensure robust inference without exceptions."""
    sample = cohort_df.head(100)
    results = agent.batch_assess(sample)
    assert len(results) == 100
    for r in results:
        assert r["severity_tier"] in ["STABLE", "MODERATE", "HIGH", "CRITICAL"]
        assert 0.0 <= r["p_mortality"] <= 1.0
        assert 0.0 <= r["p_deterioration"] <= 1.0
        assert len(r["recommended_action"]) > 0

def test_archetype_septic_shock(agent):
    """Clinical Archetype 1: Severe Septic Shock."""
    pt = {
        "heartrate_mean": 132.0, "heartrate_max": 145.0, "heartrate_std": 18.0,
        "meanbp_min": 52.0, "sbp_min": 78.0, "temperature_max": 39.5,
        "wbc_max": 19.5, "lactate_max": 5.8, "resprate_max": 32.0
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-SEPTIC-01")
    assert assessment.severity.final_tier in ["HIGH", "CRITICAL"]
    active_pat = [p.pattern_name for p in assessment.patterns if p.detected]
    assert any("Septic" in p for p in active_pat)

def test_archetype_cardiogenic_shock(agent):
    """Clinical Archetype 2: Cardiogenic Shock with Narrow Pulse Pressure."""
    pt = {
        "heartrate_mean": 118.0, "sbp_min": 82.0, "dbp_min": 62.0,
        "pulse_pressure": 20.0, "shock_index_max": 1.25, "sao2_min": 88.0, "meanbp_min": 58.0
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-CARDIO-02")
    active_pat = [p.pattern_name for p in assessment.patterns if p.detected]
    assert any("Cardiogenic" in p for p in active_pat)

def test_archetype_ards(agent):
    """Clinical Archetype 3: Acute Respiratory Distress Syndrome."""
    pt = {
        "sao2_min": 82.0, "pao2_min": 52.0, "resprate_max": 36.0,
        "heartrate_mean": 98.0, "meanbp_min": 74.0
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-ARDS-03")
    assert assessment.organ_assessments["Respiratory"].grade >= 2
    active_pat = [p.pattern_name for p in assessment.patterns if p.detected]
    assert any("ARDS" in p or "Type 1" in p for p in active_pat)

def test_archetype_hemorrhagic_shock(agent):
    """Clinical Archetype 4: Hemorrhagic Shock with Acute Blood Loss."""
    pt = {
        "hemoglobin_min": 6.2, "heartrate_max": 130.0, "meanbp_min": 58.0,
        "sbp_min": 80.0, "shock_index_max": 1.3
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-HEM-04")
    active_pat = [p.pattern_name for p in assessment.patterns if p.detected]
    assert any("Hemorrhagic" in p for p in active_pat)

def test_archetype_hepatorenal_syndrome(agent):
    """Clinical Archetype 5: Hepatorenal Syndrome (HRS-AKI)."""
    pt = {
        "bilirubin_max": 4.8, "inr_max": 2.2, "creatinine_max": 3.1,
        "bun_max": 58.0, "meanbp_min": 72.0
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-HRS-05")
    active_pat = [p.pattern_name for p in assessment.patterns if p.detected]
    assert any("Hepatorenal" in p for p in active_pat)

def test_archetype_hyperosmolar_crisis(agent):
    """Clinical Archetype 6: DKA / Hyperosmolar Crisis."""
    pt = {
        "glucose_max": 420.0, "ph_min": 7.18, "sodium_mean": 150.0,
        "heartrate_mean": 115.0
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-DKA-06")
    active_pat = [p.pattern_name for p in assessment.patterns if p.detected]
    assert any("Hyperosmolar" in p for p in active_pat)

def test_archetype_stable_patient(agent):
    """Clinical Archetype 7: Completely Stable ICU Patient."""
    pt = {
        "heartrate_mean": 72.0, "heartrate_min": 65.0, "heartrate_max": 80.0,
        "meanbp_min": 78.0, "meanbp_mean": 85.0, "sbp_min": 118.0,
        "sao2_min": 98.0, "resprate_max": 15.0, "creatinine_max": 0.8,
        "lactate_max": 1.1, "gcs_min": 15.0, "temperature_max": 36.8
    }
    assessment = agent.full_assessment(pt, patient_id="ARCH-STABLE-07")
    assert assessment.severity.final_tier == "STABLE"
    assert not assessment.severity.escalation_occurred
    assert len(assessment.severity.active_red_flags) == 0
