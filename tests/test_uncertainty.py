"""Unit tests for Uncertainty Quantification in ICU Guard v5.0."""
import pytest
from severity_agent.uncertainty import UncertaintyQuantifier

def test_uncertainty_quantifier_basic():
    uq = UncertaintyQuantifier(bootstrap_samples=25)
    probs = {"p_mortality": 0.35, "p_deterioration": 0.55, "p_severe": 0.45}
    vitals = {
        "meanbp_min": 65.0,
        "heartrate_mean": 92.0,
        "lactate_max": 2.8,
        "creatinine_max": 1.6,
        "sao2_min": 94.0
    }
    report = uq.quantify(probabilities=probs, vitals=vitals, missingness_pct=15.0)

    assert "mortality" in report.targets
    assert "deterioration" in report.targets
    assert "severe" in report.targets

    # Verify Conformal prediction interval bounds
    mort = report.targets["mortality"]
    assert mort.conformal_lower <= mort.point_estimate <= mort.conformal_upper
    assert mort.interval_width > 0.0

    # Verify Bootstrap CI bounds
    assert mort.ci_lower <= mort.point_estimate <= mort.ci_upper

    # Check uncertainty metrics
    assert 0.0 <= report.composite_uncertainty_score <= 1.0
    assert 0.0 <= report.epistemic_score <= 1.0
    assert 0.0 <= report.aleatoric_score <= 1.0
    assert report.reliability_tier in ["RELIABLE", "CAUTION", "HIGH_UNCERTAINTY"]
    assert len(report.clinical_advisory) > 0

def test_uncertainty_ood_detection():
    uq = UncertaintyQuantifier()
    probs = {"p_mortality": 0.20, "p_deterioration": 0.30, "p_severe": 0.20}
    # Completely anomalous extreme vital values (Covariate shift / sensor error)
    vitals_ood = {
        "meanbp_min": 195.0,
        "heartrate_mean": 210.0,
        "creatinine_max": 18.0,
        "lactate_max": 24.0,
    }
    report = uq.quantify(probabilities=probs, vitals=vitals_ood, missingness_pct=60.0)
    assert report.ood_score > 0.6
    assert report.reliability_tier in ["CAUTION", "HIGH_UNCERTAINTY"]

def test_uncertainty_to_dict():
    uq = UncertaintyQuantifier()
    report = uq.quantify({"p_mortality": 0.10}, {"meanbp_min": 75.0})
    d = report.to_dict()
    assert "composite_uncertainty" in d
    assert "reliability_tier" in d
    assert "targets" in d
