"""Unit tests for LLM Copilot advisory modules and safety guardrails."""
import pytest
from severity_agent.llm_copilot import (
    PHIScrubber,
    stamp_advisory,
    ADVISORY_WATERMARK,
    LLMClient,
    ClinicalReviewer,
    BedsideClinicalChat,
    SBARGenerator,
    WhatIfSimulator
)

def test_phi_scrubber():
    raw = {
        "patientunitstayid": 1234567,
        "uniquepid": "002-1234",
        "mrn": "MRN-9988",
        "name": "Jane Doe",
        "heartrate_mean": 88.0,
        "meanbp_min": 64.0,
        "lactate_max": 2.2
    }
    cleaned = PHIScrubber.sanitize_features(raw)
    assert "patientunitstayid" not in cleaned
    assert "uniquepid" not in cleaned
    assert "mrn" not in cleaned
    assert "name" not in cleaned
    assert cleaned["heartrate_mean"] == 88.0
    assert cleaned["meanbp_min"] == 64.0

def test_advisory_watermarking():
    text = "Initiate norepinephrine infusion."
    watermarked = stamp_advisory(text)
    assert "CLINICAL DECISION SUPPORT ADVISORY" in watermarked
    assert "sole legal responsibility" in watermarked
    # Ensure idempotency
    assert stamp_advisory(watermarked) == watermarked

def test_copilot_reviewer_offline():
    reviewer = ClinicalReviewer(LLMClient(api_key=None))
    summary = {
        "severity_tier": "CRITICAL",
        "overall_score": 9.2,
        "active_red_flags": ["MAP < 50 mmHg"],
        "primary_etiology": "Infection / Sepsis",
        "trajectory": "RAPID_DETERIORATION"
    }
    vitals = {"meanbp_min": 48.0, "heartrate_mean": 130.0}
    rev = reviewer.review(summary, vitals)
    assert "SECOND OPINION" in rev
    assert "CRITICAL" in rev
    assert "CLINICAL DECISION SUPPORT ADVISORY" in rev

def test_copilot_chat_offline():
    chat = BedsideClinicalChat(LLMClient(api_key=None))
    summary = {"severity_tier": "HIGH", "primary_etiology": "Sepsis"}
    vitals = {"lactate_max": 4.5}
    ans = chat.ask("What is the recommended fluid bolus volume?", summary, vitals)
    assert "30 mL/kg" in ans
    assert "Surviving Sepsis" in ans

def test_copilot_sbar_generation():
    sbar_gen = SBARGenerator(LLMClient(api_key=None))
    summary = {
        "severity_tier": "HIGH",
        "overall_score": 7.5,
        "trajectory": "INDOLENT_DETERIORATION",
        "primary_etiology": "Distributive Shock",
        "active_red_flags": [],
        "recommended_action": "Evaluate fluid response"
    }
    vitals = {"heartrate_mean": 105.0, "meanbp_min": 62.0, "has_diabetes": 1}
    report = sbar_gen.generate(summary, vitals)
    assert "[S] SITUATION" in report
    assert "[B] BACKGROUND" in report
    assert "[A] ASSESSMENT" in report
    assert "[R] RECOMMENDATION" in report
    assert "Diabetes Mellitus" in report

def test_copilot_what_if_simulation():
    sim = WhatIfSimulator(LLMClient(api_key=None))
    summary = {"severity_tier": "HIGH", "primary_etiology": "Septic Shock"}
    vitals = {"meanbp_min": 58.0, "lactate_max": 4.2}
    sim_out = sim.simulate("What if we infuse 30 mL/kg normal saline?", summary, vitals)
    assert "WHAT-IF SCENARIO" in sim_out
    assert "Physiological Response" in sim_out
    assert "Safety Monitoring" in sim_out
