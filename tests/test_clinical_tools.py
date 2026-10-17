"""Unit tests for bedside clinical tools (trends, similarity, recommendations, audit)."""
import os
import tempfile
import pytest
from severity_agent.trends import TrendAnalyzer
from severity_agent.similarity import PatientSimilarityEngine
from severity_agent.recommendations import RecommendationEngine
from severity_agent.audit import RegulatoryAuditLogger
from severity_agent.detectors import OrganAssessment

def test_trend_analyzer_instability():
    analyzer = TrendAnalyzer()
    vitals_volatile = {
        "heartrate_min": 65.0,
        "heartrate_max": 145.0,
        "heartrate_mean": 95.0,
        "heartrate_std": 22.5,
        "meanbp_min": 48.0,
        "meanbp_max": 95.0,
        "meanbp_std": 17.0,
        "respiration_max": 34.0,
        "respiration_std": 8.0
    }
    report = analyzer.analyze(vitals_volatile)
    assert report.autonomic_instability_detected
    assert report.overall_direction in ["VOLATILE", "RAPID_DECOMPENSATION"]
    assert len(report.clinical_flags) >= 2
    assert "heartrate" in report.variable_trends
    assert "meanbp" in report.variable_trends

def test_patient_similarity_engine():
    engine = PatientSimilarityEngine()
    vitals = {
        "meanbp_min": 60.0,
        "heartrate_mean": 110.0,
        "lactate_max": 4.5,
        "creatinine_max": 2.8,
        "age_clean": 68.0
    }
    rep = engine.find_similar_cases(vitals, k=3, query_patient_id="TEST-SIM-01")
    assert rep.query_patient_id == "TEST-SIM-01"
    # If cohort is loaded, check matches
    if rep.top_matches:
        assert len(rep.top_matches) <= 3
        assert 0.0 <= rep.top_matches[0].similarity_score <= 1.0
        assert 0.0 <= rep.cohort_deterioration_rate_pct <= 100.0

def test_recommendation_engine():
    engine = RecommendationEngine()
    organs = {
        "Sepsis": OrganAssessment(organ_name="Sepsis", grade=2, description="Septic condition"),
        "Renal": OrganAssessment(organ_name="Renal", grade=2, description="KDIGO 2 AKI")
    }
    plan = engine.generate_plan(
        severity_tier="CRITICAL",
        organ_assessments=organs,
        patterns=[],
        vitals={"lactate_max": 5.0}
    )
    assert "Surviving Sepsis" in plan.primary_protocol
    assert len(plan.stat_actions) >= 1
    assert any("blood culture" in a.lower() for a in plan.stat_actions)
    assert any("KDIGO" in it.guideline_source for it in plan.items)

def test_regulatory_audit_logger():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        logger = RegulatoryAuditLogger(log_path=tmp_path)
        # Log 3 sequential assessments
        r1 = logger.log_assessment(
            patient_id="P1", inputs={"hr": 80}, probabilities={"p_m": 0.1},
            severity_tier="STABLE", escalation_occurred=False, escalation_reasons=[],
            active_red_flags=[], validation_status="PASSED"
        )
        r2 = logger.log_assessment(
            patient_id="P2", inputs={"hr": 140}, probabilities={"p_m": 0.8},
            severity_tier="CRITICAL", escalation_occurred=True, escalation_reasons=["MAP < 50"],
            active_red_flags=["MAP < 50"], validation_status="PASSED"
        )
        
        # Verify hash chaining
        assert r2.prev_record_hash == r1.record_hash
        assert len(r1.record_hash) == 64
        assert len(r2.record_hash) == 64

        # Verify ledger cryptographic integrity
        valid, count, msg = logger.verify_ledger(tmp_path)
        assert valid
        assert count == 2
        assert "verified" in msg.lower()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
