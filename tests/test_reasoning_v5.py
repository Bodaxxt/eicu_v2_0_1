"""Unit tests for Advanced Clinical Reasoning Engine in ICU Guard v5.0."""
import pytest
from severity_agent.reasoning import ClinicalReasoningEngine
from severity_agent.detectors import OrganAssessment

def test_causal_graph_and_multihypothesis():
    engine = ClinicalReasoningEngine()
    organs = {
        "Sepsis": OrganAssessment(organ_name="Sepsis", grade=2, description="Septic condition"),
        "Hemodynamic": OrganAssessment(organ_name="Hemodynamic", grade=2, description="Hypotension"),
        "Renal": OrganAssessment(organ_name="Renal", grade=2, description="Oliguria KDIGO 2"),
        "Respiratory": OrganAssessment(organ_name="Respiratory", grade=1, description="Mild tachypnea"),
        "Hepatic": OrganAssessment(organ_name="Hepatic", grade=0, description="Normal"),
    }
    vitals = {
        "heartrate_std": 19.0,
        "meanbp_std": 16.0,
        "shock_index_max": 1.25,
        "lactate_max": 4.5
    }
    probs = {"p_mortality": 0.48, "p_deterioration": 0.72, "p_severe": 0.65}

    report = engine.analyze(
        probabilities=probs,
        organ_assessments=organs,
        patterns=[],
        vitals=vitals
    )

    # 1. Causal Graph
    assert len(report.causal_graph) > 0
    assert "Sepsis" in report.causal_graph or "Vasodilatory Distributive Shock" in report.causal_graph

    # 2. Multi-Hypothesis Tracking
    assert len(report.differential_diagnosis) == 3
    top_diff = report.differential_diagnosis[0]
    assert len(top_diff.supporting_evidence) > 0
    assert len(top_diff.action_priority) > 0
    assert len(top_diff.guideline_matches) > 0

    # 3. Trajectory & 12h Risk Projection
    assert report.trajectory == "RAPID_DETERIORATION"
    assert "projected_p_deterioration_12h" in report.projected_trajectory_12h
    assert report.projected_trajectory_12h["projected_p_deterioration_12h"] >= probs["p_deterioration"]

    # 4. Counterfactual Scenarios
    assert len(report.counterfactual_scenarios) >= 1
    cf = report.counterfactual_scenarios[0]
    assert "intervention" in cf
    assert "clinical_impact" in cf

    # 5. Guideline Adherence Matching
    assert any("Surviving Sepsis" in g or "KDIGO" in g for g in report.guideline_adherence)
