"""
ICU Guard v5.0 — Phase 3 Final Assessment Tests
=================================================
Comprehensive unit and integration tests for:
- action_list component logic
- narrative_view component import
- uncertainty_view component logic
- sbar_modal component logic
- chat_window component logic
- pdf_export utility
- DataLoader.get_patient_row()
- final_assessment page import and routing
"""

import pytest
import io
from typing import Dict, Any, List

# ─────────────────────────────────────────────────────────────
# Fixtures: Clinical Archetypes
# ─────────────────────────────────────────────────────────────
from severity_agent.recommendations import (
    ActionablePlan,
    ClinicalActionItem,
    RecommendationEngine,
)
from severity_agent.uncertainty import UncertaintyQuantifier, UncertaintyReport
from severity_agent.detectors import (
    OrganAssessment,
    RespiratoryDetector,
    RenalDetector,
)
from severity_agent.patterns import SepticShockPattern, ARDSPattern
from severity_agent.severity import SeverityEvaluator, SeverityAssessment


@pytest.fixture
def septic_vitals() -> Dict[str, Any]:
    return {
        "heartrate_mean": 128.0,
        "heartrate_max": 145.0,
        "heartrate_std": 18.0,
        "meanbp_min": 52.0,
        "meanbp_max": 66.0,
        "meanbp_std": 8.0,
        "respiration_max": 32.0,
        "temperature_max": 39.4,
        "sao2_min": 87.0,
        "gcs_min": 11.0,
        "lactate_max": 5.8,
        "wbc_max": 21.0,
        "creatinine_max": 2.9,
        "bilirubin_max": 2.1,
        "platelets_min": 90.0,
        "vasopressor_6h": 1,
        "ventilation_6h": 0,
        "has_diabetes": 1,
        "has_hypertension": 0,
    }


@pytest.fixture
def stable_vitals() -> Dict[str, Any]:
    return {
        "heartrate_mean": 74.0,
        "heartrate_max": 85.0,
        "heartrate_std": 5.0,
        "meanbp_min": 80.0,
        "meanbp_std": 4.0,
        "respiration_max": 16.0,
        "temperature_max": 37.0,
        "sao2_min": 98.0,
        "gcs_min": 15.0,
        "lactate_max": 1.0,
        "creatinine_max": 0.9,
        "platelets_min": 210.0,
        "vasopressor_6h": 0,
        "ventilation_6h": 0,
    }


@pytest.fixture
def sample_action_plan() -> ActionablePlan:
    return ActionablePlan(
        primary_protocol="Surviving Sepsis Hour-1 Resuscitation Bundle",
        items=[
            ClinicalActionItem(
                category="DIAGNOSTIC",
                action_text="Draw two sets of blood cultures prior to antibiotics.",
                urgency="STAT",
                guideline_source="SSC 2021",
                rationale="Identify causative pathogen before antimicrobial therapy.",
            ),
            ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Administer empiric broad-spectrum IV antimicrobials within 1 hour.",
                urgency="STAT",
                guideline_source="SSC 2021",
                rationale="Delay increases mortality 7.6% per hour.",
            ),
            ClinicalActionItem(
                category="MONITORING",
                action_text="Remonitor lactate in 2-4 hours.",
                urgency="1_HOUR",
                guideline_source="SSC 2021",
                rationale="Lactate clearance > 20% confirms resuscitation.",
            ),
            ClinicalActionItem(
                category="MONITORING",
                action_text="Continuous ECG and haemodynamic monitoring.",
                urgency="ROUTINE",
                guideline_source="Critical Care Core Protocols",
                rationale="Baseline surveillance.",
            ),
        ],
        stat_actions=["Draw two sets of blood cultures.", "Empiric broad-spectrum antimicrobials."],
        contraindications_and_cautions=["CAUTION: Avoid rapid large-volume boluses in suspected cardiac failure."],
    )


@pytest.fixture
def sample_uncertainty(septic_vitals) -> UncertaintyReport:
    probs = {"p_mortality": 0.72, "p_deterioration": 0.68, "p_severe": 0.81}
    uq = UncertaintyQuantifier(bootstrap_samples=20)
    return uq.quantify(probs, septic_vitals, missingness_pct=12.0)


# ─────────────────────────────────────────────────────────────
# 1. Action List Logic Tests
# ─────────────────────────────────────────────────────────────
class TestActionListLogic:
    def test_plan_has_items(self, sample_action_plan):
        assert len(sample_action_plan.items) == 4

    def test_stat_urgency_count(self, sample_action_plan):
        stat_count = sum(
            1 for it in sample_action_plan.items if it.urgency in ("STAT", "15_MIN")
        )
        assert stat_count == 2

    def test_cautions_present(self, sample_action_plan):
        assert len(sample_action_plan.contraindications_and_cautions) == 1
        assert "cardiac" in sample_action_plan.contraindications_and_cautions[0].lower()

    def test_recommendation_engine_sepsis(self, septic_vitals):
        """Engine generates sepsis protocol for high-vitals patient."""
        from severity_agent.detectors import (
            SepsisDetector, RespiratoryDetector, HemodynamicDetector,
            RenalDetector, NeurologicalDetector, HepaticDetector,
            CoagulationDetector, MetabolicDetector, EndocrineDetector,
            HematologicDetector, NutritionalDetector,
        )
        from severity_agent.patterns import SepticShockPattern

        organs = {
            "Sepsis":       SepsisDetector().assess(septic_vitals),
            "Respiratory":  RespiratoryDetector().assess(septic_vitals),
            "Hemodynamic":  HemodynamicDetector().assess(septic_vitals),
            "Renal":        RenalDetector().assess(septic_vitals),
            "Neurological": NeurologicalDetector().assess(septic_vitals),
            "Hepatic":      HepaticDetector().assess(septic_vitals),
            "Coagulation":  CoagulationDetector().assess(septic_vitals),
            "Metabolic":    MetabolicDetector().assess(septic_vitals),
            "Endocrine":    EndocrineDetector().assess(septic_vitals),
            "Hematologic":  HematologicDetector().assess(septic_vitals),
            "Nutritional":  NutritionalDetector().assess(septic_vitals),
        }

        patt = SepticShockPattern()
        patt_result = patt.evaluate(organs, septic_vitals)
        patterns = [patt_result]

        engine = RecommendationEngine()
        plan = engine.generate_plan("CRITICAL", organs, patterns, septic_vitals)
        assert plan is not None
        assert len(plan.items) >= 3
        assert any(it.urgency == "STAT" for it in plan.items)
        assert "Sepsis" in plan.primary_protocol or "Resuscitation" in plan.primary_protocol

    def test_recommendation_engine_stable(self, stable_vitals):
        """Engine generates routine protocol for stable patient."""
        from severity_agent.detectors import (
            SepsisDetector, RespiratoryDetector, HemodynamicDetector,
            RenalDetector, NeurologicalDetector, HepaticDetector,
            CoagulationDetector, MetabolicDetector, EndocrineDetector,
            HematologicDetector, NutritionalDetector,
        )
        organs = {
            "Sepsis":       SepsisDetector().assess(stable_vitals),
            "Respiratory":  RespiratoryDetector().assess(stable_vitals),
            "Hemodynamic":  HemodynamicDetector().assess(stable_vitals),
            "Renal":        RenalDetector().assess(stable_vitals),
            "Neurological": NeurologicalDetector().assess(stable_vitals),
            "Hepatic":      HepaticDetector().assess(stable_vitals),
            "Coagulation":  CoagulationDetector().assess(stable_vitals),
            "Metabolic":    MetabolicDetector().assess(stable_vitals),
            "Endocrine":    EndocrineDetector().assess(stable_vitals),
            "Hematologic":  HematologicDetector().assess(stable_vitals),
            "Nutritional":  NutritionalDetector().assess(stable_vitals),
        }
        engine = RecommendationEngine()
        plan = engine.generate_plan("STABLE", organs, [], stable_vitals)
        assert plan is not None
        assert any(it.urgency == "ROUTINE" for it in plan.items)


# ─────────────────────────────────────────────────────────────
# 2. Uncertainty View Logic Tests
# ─────────────────────────────────────────────────────────────
class TestUncertaintyView:
    def test_report_generated(self, sample_uncertainty):
        assert sample_uncertainty is not None

    def test_reliability_tier_valid(self, sample_uncertainty):
        assert sample_uncertainty.reliability_tier in (
            "RELIABLE", "CAUTION", "HIGH_UNCERTAINTY"
        )

    def test_composite_score_bounded(self, sample_uncertainty):
        assert 0.0 <= sample_uncertainty.composite_uncertainty_score <= 1.0

    def test_targets_present(self, sample_uncertainty):
        assert "mortality" in sample_uncertainty.targets
        assert "deterioration" in sample_uncertainty.targets

    def test_ci_bounds_valid(self, sample_uncertainty):
        for tgt in sample_uncertainty.targets.values():
            assert tgt.conformal_lower <= tgt.conformal_upper
            assert 0.0 <= tgt.conformal_lower <= 1.0
            assert 0.0 <= tgt.conformal_upper <= 1.0

    def test_ood_score_bounded(self, sample_uncertainty):
        assert 0.0 <= sample_uncertainty.ood_score <= 1.0

    def test_high_uncertainty_flagged_for_extreme_patient(self):
        """A patient with extreme OOD vitals should not return RELIABLE."""
        extreme_vitals = {
            "heartrate_mean": 220.0,
            "meanbp_min": 20.0,
            "respiration_max": 60.0,
            "lactate_max": 18.0,
        }
        probs = {"p_mortality": 0.95, "p_deterioration": 0.93, "p_severe": 0.98}
        uq = UncertaintyQuantifier()
        report = uq.quantify(probs, extreme_vitals, missingness_pct=40.0)
        assert report.reliability_tier in ("CAUTION", "HIGH_UNCERTAINTY")

    def test_reliable_for_normal_patient(self, stable_vitals):
        probs = {"p_mortality": 0.08, "p_deterioration": 0.10, "p_severe": 0.12}
        uq = UncertaintyQuantifier()
        report = uq.quantify(probs, stable_vitals, missingness_pct=0.0)
        # Stable in-distribution patient should not be HIGH_UNCERTAINTY
        assert report.reliability_tier != "HIGH_UNCERTAINTY"


# ─────────────────────────────────────────────────────────────
# 3. SBAR Generator Tests
# ─────────────────────────────────────────────────────────────
class TestSBARGenerator:
    def test_sbar_contains_all_sections(self, septic_vitals):
        from severity_agent.llm_copilot.sbar import SBARGenerator

        assessment_dict = {
            "severity_tier": "CRITICAL",
            "overall_score": 8.5,
            "trajectory": "DETERIORATING",
            "primary_etiology": "Septic Shock with Multi-Organ Dysfunction",
            "active_red_flags": ["Lactate > 4.0 mmol/L", "MAP < 65 mmHg"],
            "patterns": [{"name": "Septic Shock"}],
            "recommended_action": "Initiate Hour-1 SSC Bundle immediately.",
        }
        sbar = SBARGenerator()
        text = sbar.generate(assessment_dict, septic_vitals, shift_notes="Night handoff")
        for section in ("[S]", "[B]", "[A]", "[R]"):
            assert section in text, f"Missing SBAR section {section}"

    def test_sbar_redacts_patient_name(self, septic_vitals):
        from severity_agent.llm_copilot.sbar import SBARGenerator

        vitals_with_name = {**septic_vitals, "patient_name": "John Doe"}
        assessment_dict = {
            "severity_tier": "HIGH",
            "overall_score": 6.0,
            "trajectory": "STABLE",
            "primary_etiology": "Pneumonia",
            "active_red_flags": [],
            "patterns": [],
            "recommended_action": "Monitor.",
        }
        sbar = SBARGenerator()
        text = sbar.generate(assessment_dict, vitals_with_name)
        assert "John Doe" not in text

    def test_sbar_advisory_watermark(self, septic_vitals):
        from severity_agent.llm_copilot.sbar import SBARGenerator
        from severity_agent.llm_copilot.safety import ADVISORY_WATERMARK

        assessment_dict = {
            "severity_tier": "STABLE",
            "overall_score": 2.5,
            "trajectory": "STABLE",
            "primary_etiology": "Post-op Monitoring",
            "active_red_flags": [],
            "patterns": [],
            "recommended_action": "Routine monitoring.",
        }
        sbar = SBARGenerator()
        text = sbar.generate(assessment_dict, septic_vitals)
        assert ADVISORY_WATERMARK.strip() in text


# ─────────────────────────────────────────────────────────────
# 4. Chat Window Logic Tests
# ─────────────────────────────────────────────────────────────
class TestBedsideClinicalChat:
    def test_chat_responds_offline(self, septic_vitals):
        from severity_agent.llm_copilot.chat import BedsideClinicalChat

        chat = BedsideClinicalChat()
        assessment_dict = {
            "severity_tier": "CRITICAL",
            "trajectory": "DETERIORATING",
            "primary_etiology": "Septic Shock",
            "active_red_flags": ["Lactate > 4"],
        }
        response = chat.ask("fluid recommendation?", assessment_dict, septic_vitals)
        assert len(response) > 20
        assert isinstance(response, str)

    def test_chat_vasopressor_query(self, septic_vitals):
        from severity_agent.llm_copilot.chat import BedsideClinicalChat

        chat = BedsideClinicalChat()
        assessment_dict = {
            "severity_tier": "CRITICAL",
            "trajectory": "DETERIORATING",
            "primary_etiology": "Septic Shock",
            "active_red_flags": [],
        }
        response = chat.ask("norepinephrine dosing for vasopressor support?", assessment_dict, septic_vitals)
        assert "norepinephrine" in response.lower() or "map" in response.lower() or "vasopressor" in response.lower()

    def test_chat_session_reset(self, septic_vitals):
        from severity_agent.llm_copilot.chat import BedsideClinicalChat

        chat = BedsideClinicalChat()
        assessment_dict = {
            "severity_tier": "MODERATE",
            "trajectory": "STABLE",
            "primary_etiology": "AKI",
            "active_red_flags": [],
        }
        chat.ask("creatinine management?", assessment_dict, septic_vitals)
        assert len(chat.history) == 2
        chat.reset_session()
        assert len(chat.history) == 0

    def test_chat_multi_turn_context(self, septic_vitals):
        from severity_agent.llm_copilot.chat import BedsideClinicalChat

        chat = BedsideClinicalChat()
        assessment_dict = {
            "severity_tier": "HIGH",
            "trajectory": "DETERIORATING",
            "primary_etiology": "Respiratory Failure",
            "active_red_flags": [],
        }
        chat.ask("antibiotic recommendation?", assessment_dict, septic_vitals)
        chat.ask("fluid strategy?", assessment_dict, septic_vitals)
        assert len(chat.history) == 4  # 2 user + 2 assistant


# ─────────────────────────────────────────────────────────────
# 5. PDF Export Tests
# ─────────────────────────────────────────────────────────────
class TestPDFExport:
    @pytest.fixture
    def assessment_dict_critical(self) -> Dict[str, Any]:
        return {
            "severity_tier": "CRITICAL",
            "overall_score": 8.7,
            "escalation_occurred": True,
            "escalation_reasons": ["Lactate > 4.0 mmol/L"],
            "trajectory": "DETERIORATING",
            "primary_etiology": "Septic Shock with MOF",
            "active_red_flags": ["Lactate > 4.0"],
            "probabilities": {
                "p_mortality": 0.74,
                "p_deterioration": 0.69,
                "p_severe": 0.82,
            },
            "organs": {
                "Respiratory": {"grade": 2, "description": "Severe ARDS", "evidence": ["PaO2/FiO2 < 100"]},
                "Renal": {"grade": 2, "description": "Stage 3 AKI", "evidence": ["Creatinine 3.2 mg/dL"]},
            },
            "patterns": [
                {"name": "Septic Shock", "confidence": "HIGH", "urgency": "CRITICAL",
                 "recommendation": "SSC Hour-1 Bundle."}
            ],
            "recommendations": {
                "protocol": "Surviving Sepsis Hour-1 Bundle",
                "stat_actions": ["Blood cultures x2", "Broad-spectrum antimicrobials"],
                "cautions": ["Avoid large bolus in cardiac failure"],
            },
            "uncertainty": {
                "reliability_tier": "CAUTION",
                "composite_uncertainty": 0.45,
                "epistemic_uncertainty": 0.30,
                "aleatoric_uncertainty": 0.22,
                "ood_score": 0.38,
                "advisory": "Moderate uncertainty detected.",
            },
            "recommended_action": "Initiate SSC Hour-1 Bundle immediately.",
        }

    def test_pdf_returns_bytes(self, assessment_dict_critical, septic_vitals):
        from dashboard.utils.pdf_export import export_pdf

        pdf_bytes = export_pdf(
            patient_id="TEST-001",
            assessment_dict=assessment_dict_critical,
            patient_vitals=septic_vitals,
            english_report="Test narrative",
            sbar_text="",
        )
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000  # Valid PDF is never tiny

    def test_pdf_starts_with_header(self, assessment_dict_critical, septic_vitals):
        from dashboard.utils.pdf_export import export_pdf

        pdf_bytes = export_pdf(
            patient_id="TEST-002",
            assessment_dict=assessment_dict_critical,
            patient_vitals=septic_vitals,
        )
        # ReportLab PDFs start with %PDF
        assert pdf_bytes[:4] == b"%PDF"

    def test_pdf_includes_stable_patient(self, stable_vitals):
        from dashboard.utils.pdf_export import export_pdf

        stable_dict = {
            "severity_tier": "STABLE",
            "overall_score": 2.1,
            "escalation_occurred": False,
            "escalation_reasons": [],
            "trajectory": "STABLE",
            "primary_etiology": "Post-op Monitoring",
            "active_red_flags": [],
            "probabilities": {"p_mortality": 0.05, "p_deterioration": 0.08, "p_severe": 0.07},
            "organs": {},
            "patterns": [],
            "recommendations": None,
            "recommended_action": "Routine monitoring.",
        }
        pdf_bytes = export_pdf(
            patient_id="TEST-003",
            assessment_dict=stable_dict,
            patient_vitals=stable_vitals,
        )
        assert pdf_bytes[:4] == b"%PDF"

    def test_pdf_write_to_disk(self, assessment_dict_critical, septic_vitals, tmp_path):
        from dashboard.utils.pdf_export import export_pdf

        out = str(tmp_path / "test_report.pdf")
        export_pdf(
            patient_id="TEST-DISK",
            assessment_dict=assessment_dict_critical,
            patient_vitals=septic_vitals,
            output_path=out,
        )
        import os
        assert os.path.exists(out)
        assert os.path.getsize(out) > 1000


# ─────────────────────────────────────────────────────────────
# 6. DataLoader.get_patient_row() Tests
# ─────────────────────────────────────────────────────────────
class TestDataLoaderGetPatientRow:
    def test_returns_dict_or_none(self):
        from dashboard.utils.data_loader import get_data_loader

        loader = get_data_loader()
        # Load a random patient
        p = loader.get_random_patient()
        pid = p.get("id")
        row = loader.get_patient_row(pid)
        assert row is not None
        assert isinstance(row, dict)

    def test_row_contains_id_column(self):
        from dashboard.utils.data_loader import get_data_loader

        loader = get_data_loader()
        p = loader.get_random_patient()
        row = loader.get_patient_row(p.get("id"))
        assert "id" in row

    def test_invalid_patient_returns_none(self):
        from dashboard.utils.data_loader import get_data_loader

        loader = get_data_loader()
        row = loader.get_patient_row("NONEXISTENT_PATIENT_9999")
        assert row is None

    def test_row_has_numeric_vitals(self):
        from dashboard.utils.data_loader import get_data_loader

        loader = get_data_loader()
        p = loader.get_random_patient()
        row = loader.get_patient_row(p.get("id"))
        assert row is not None
        # At least some numeric values should exist
        numeric_cols = [k for k, v in row.items() if isinstance(v, (int, float))]
        assert len(numeric_cols) > 10


# ─────────────────────────────────────────────────────────────
# 7. Final Assessment Page Import Test
# ─────────────────────────────────────────────────────────────
class TestFinalAssessmentPageImport:
    def test_module_importable(self):
        """final_assessment page must import without errors."""
        from dashboard.pages import final_assessment  # noqa: F401
        assert hasattr(final_assessment, "final_assessment_page")

    def test_function_callable(self):
        from dashboard.pages.final_assessment import final_assessment_page
        assert callable(final_assessment_page)


# ─────────────────────────────────────────────────────────────
# 8. Narrative Generator Tests
# ─────────────────────────────────────────────────────────────
class TestNarrativeGenerator:
    def test_english_report_non_empty(self, septic_vitals):
        from severity_agent.narrative import ClinicalNarrativeGenerator
        from severity_agent.severity import SeverityEvaluator
        from severity_agent.reasoning import ClinicalReasoningEngine
        from severity_agent.validator import PredictionValidator
        from severity_agent.detectors import (
            SepsisDetector, RespiratoryDetector, HemodynamicDetector,
            RenalDetector, NeurologicalDetector, HepaticDetector,
            CoagulationDetector, MetabolicDetector, EndocrineDetector,
            HematologicDetector, NutritionalDetector,
        )

        probs = {"p_mortality": 0.72, "p_deterioration": 0.68, "p_severe": 0.81}
        organs = {
            "Sepsis":       SepsisDetector().assess(septic_vitals),
            "Respiratory":  RespiratoryDetector().assess(septic_vitals),
            "Hemodynamic":  HemodynamicDetector().assess(septic_vitals),
            "Renal":        RenalDetector().assess(septic_vitals),
            "Neurological": NeurologicalDetector().assess(septic_vitals),
            "Hepatic":      HepaticDetector().assess(septic_vitals),
            "Coagulation":  CoagulationDetector().assess(septic_vitals),
            "Metabolic":    MetabolicDetector().assess(septic_vitals),
            "Endocrine":    EndocrineDetector().assess(septic_vitals),
            "Hematologic":  HematologicDetector().assess(septic_vitals),
            "Nutritional":  NutritionalDetector().assess(septic_vitals),
        }
        validator = PredictionValidator()
        validation = validator.validate(probs, organs, septic_vitals)
        severity = SeverityEvaluator().evaluate(probs, organs, [], septic_vitals)
        reasoning = ClinicalReasoningEngine().analyze(probs, organs, [], septic_vitals)

        gen = ClinicalNarrativeGenerator()
        en_report = gen.generate_english_report(
            "TEST-001", probs, organs, [], severity, reasoning, validation
        )
        assert len(en_report) > 200
        assert "CRITICAL CARE" in en_report or "ICU GUARD" in en_report

    def test_arabic_report_non_empty(self, septic_vitals):
        from severity_agent.narrative import ClinicalNarrativeGenerator
        from severity_agent.severity import SeverityEvaluator
        from severity_agent.reasoning import ClinicalReasoningEngine
        from severity_agent.validator import PredictionValidator
        from severity_agent.detectors import (
            SepsisDetector, RespiratoryDetector, HemodynamicDetector,
            RenalDetector, NeurologicalDetector, HepaticDetector,
            CoagulationDetector, MetabolicDetector, EndocrineDetector,
            HematologicDetector, NutritionalDetector,
        )

        probs = {"p_mortality": 0.72, "p_deterioration": 0.68, "p_severe": 0.81}
        organs = {
            "Sepsis":       SepsisDetector().assess(septic_vitals),
            "Respiratory":  RespiratoryDetector().assess(septic_vitals),
            "Hemodynamic":  HemodynamicDetector().assess(septic_vitals),
            "Renal":        RenalDetector().assess(septic_vitals),
            "Neurological": NeurologicalDetector().assess(septic_vitals),
            "Hepatic":      HepaticDetector().assess(septic_vitals),
            "Coagulation":  CoagulationDetector().assess(septic_vitals),
            "Metabolic":    MetabolicDetector().assess(septic_vitals),
            "Endocrine":    EndocrineDetector().assess(septic_vitals),
            "Hematologic":  HematologicDetector().assess(septic_vitals),
            "Nutritional":  NutritionalDetector().assess(septic_vitals),
        }
        validator = PredictionValidator()
        validation = validator.validate(probs, organs, septic_vitals)
        severity = SeverityEvaluator().evaluate(probs, organs, [], septic_vitals)
        reasoning = ClinicalReasoningEngine().analyze(probs, organs, [], septic_vitals)

        gen = ClinicalNarrativeGenerator()
        ar_report = gen.generate_arabic_report(
            "TEST-001", probs, organs, [], severity, reasoning, validation
        )
        assert len(ar_report) > 100
        assert "ICU GUARD" in ar_report or "المريض" in ar_report or "٣" in ar_report


class TestRenderComponentResilience:
    """Verifies that all render_* components execute cleanly under NiceGUI context."""

    def test_render_triage_header_with_callbacks(self, septic_vitals):
        from dashboard.components.triage_header import render_triage_header
        from severity_agent.severity import SeverityAssessment

        sev = SeverityAssessment(
            ml_base_tier="CRITICAL",
            organ_driven_tier="CRITICAL",
            final_tier="CRITICAL",
            overall_score=8.5,
            escalation_occurred=True,
            escalation_reasons=["Hypotension refractory"],
            active_red_flags=["Mean BP < 65"],
        )
        patient = {"id": "141168", "age": 68, "gender": "M", "apache": 85}

        sbar_called = []
        chat_called = []
        pdf_called = []

        # Standard call with callbacks
        render_triage_header(
            patient=patient,
            assessment=sev,
            on_sbar=lambda: sbar_called.append(1),
            on_chat=lambda: chat_called.append(1),
            on_pdf=lambda: pdf_called.append(1),
        )

        # Swapped call (severity first, patient second, no callbacks)
        render_triage_header(sev, patient)

    def test_render_risk_gauges_flexibility(self):
        from dashboard.components.risk_gauges import render_risk_gauges

        # Dict input
        probs = {"p_mortality": 0.45, "p_deterioration": 0.65, "p_severe": 0.70}
        render_risk_gauges(probs)

        # Mock object input
        class MockAssessment:
            probabilities = probs
            uncertainty = None

        render_risk_gauges(MockAssessment())

    def test_render_organ_cards_resilience(self, septic_vitals):
        from dashboard.components.organ_cards import render_organ_cards
        from severity_agent.detectors import SepsisDetector

        organs = {"Sepsis": SepsisDetector().assess(septic_vitals)}
        render_organ_cards(organs)
        render_organ_cards(None)

    def test_render_pattern_list_resilience(self):
        from dashboard.components.pattern_list import render_pattern_list
        render_pattern_list([])
        render_pattern_list(None)

    def test_render_action_list_resilience(self):
        from dashboard.components.action_list import render_action_list
        render_action_list(None)

    def test_render_narrative_view_resilience(self):
        from dashboard.components.narrative_view import render_narrative_view
        render_narrative_view("English text", "نص عربي")
        render_narrative_view("", "")

    def test_render_uncertainty_view_resilience(self):
        from dashboard.components.uncertainty_view import render_uncertainty_view
        render_uncertainty_view(None)

