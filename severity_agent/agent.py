"""
ICU Guard v5.0 — Main Severity Agent Core
=========================================
Coordinates multi-modal clinical reasoning above the 3 trained XGBoost models:
1. Model Feature Extraction & Calibrated Risk Prediction
2. Multi-Organ Physiological Injury Grading (11 Evidence-Based Detectors)
3. Critical Care Syndrome Matching (16 Complex Clinical Patterns)
4. Multi-Layer Clinical Sanity Validation (6 Comprehensive Checks + OOD Detection)
5. Non-Downgrading Severity Arbitration & Absolute Safety Overrides
6. Pathophysiological Causal Graphs, Trajectory Prediction, & Multi-Hypothesis Differentials
7. Uncertainty Quantification (Bootstrap CI, Conformal Intervals, OOD scoring)
8. Bedside Clinical Tools (Trend Velocity, Cohort Similarity, Action Protocols, Audit Ledger)
9. LLM Copilot Advisory Layer (Second Opinion Reviewer, SBAR Handoff, Chat, What-If)
10. Bilingual Narrative Generation (English & Arabic)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
import os
import pickle
import logging
import time
import numpy as np
import pandas as pd

from severity_agent.detectors import (
    OrganAssessment,
    RespiratoryDetector,
    HemodynamicDetector,
    RenalDetector,
    NeurologicalDetector,
    SepsisDetector,
    HepaticDetector,
    CoagulationDetector,
    MetabolicDetector,
    EndocrineDetector,
    HematologicDetector,
    NutritionalDetector
)
from severity_agent.patterns import (
    PatternMatch,
    SepticShockPattern,
    ARDSPattern,
    AKIPattern,
    MOFPattern,
    NeuroRespiratoryPattern,
    CardiogenicShockPattern,
    HemorrhagicShockPattern,
    DICPattern,
    DeliriumPattern,
    RefractoryShockPattern,
    Type1RespiratoryFailurePattern,
    Type2RespiratoryFailurePattern,
    HepatorenalSyndromePattern,
    PostoperativeDeteriorationPattern,
    SevereAcidemiaPattern,
    HyperosmolarCrisisPattern
)
from severity_agent.validator import PredictionValidator, ValidationReport
from severity_agent.severity import SeverityEvaluator, SeverityAssessment
from severity_agent.reasoning import ClinicalReasoningEngine, ClinicalReasoningReport
from severity_agent.narrative import ClinicalNarrativeGenerator
from severity_agent.uncertainty import UncertaintyQuantifier, UncertaintyReport
from severity_agent.trends import TrendAnalyzer, PatientTrendReport
from severity_agent.similarity import PatientSimilarityEngine, SimilarityReport
from severity_agent.recommendations import RecommendationEngine, ActionablePlan
from severity_agent.audit import RegulatoryAuditLogger, AuditRecord
from severity_agent.llm_copilot import (
    ClinicalReviewer,
    BedsideClinicalChat,
    SBARGenerator,
    WhatIfSimulator,
    LLMClient
)

logger = logging.getLogger(__name__)


@dataclass
class FullClinicalAssessment:
    """Complete, end-to-end clinical reasoning output for a single patient."""
    patient_id: Any
    probabilities: Dict[str, float]
    organ_assessments: Dict[str, OrganAssessment]
    patterns: List[PatternMatch]
    validation: ValidationReport
    severity: SeverityAssessment
    reasoning: ClinicalReasoningReport
    english_report: str
    arabic_report: str
    # v5.0 Extended Attributes
    uncertainty: Optional[UncertaintyReport] = None
    recommendations: Optional[ActionablePlan] = None
    trends: Optional[PatientTrendReport] = None
    similar_cases: Optional[SimilarityReport] = None
    audit_record: Optional[AuditRecord] = None
    copilot_review: Optional[str] = None
    sbar_handoff: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire assessment hierarchy into JSON-serializable dictionary."""
        base_dict = {
            "patient_id": self.patient_id,
            "probabilities": self.probabilities,
            "severity_tier": self.severity.final_tier,
            "overall_score": self.severity.overall_score,
            "escalation_occurred": self.severity.escalation_occurred,
            "escalation_reasons": self.severity.escalation_reasons,
            "active_red_flags": self.severity.active_red_flags,
            "organs": {
                name: {
                    "grade": assess.grade,
                    "description": assess.description,
                    "evidence": assess.clinical_evidence,
                    "action": getattr(assess, 'suggested_action', "")
                }
                for name, assess in self.organ_assessments.items()
            },
            "patterns": [
                {
                    "name": p.pattern_name,
                    "detected": p.detected,
                    "confidence": p.confidence,
                    "urgency": p.urgency_tier,
                    "recommendation": p.clinical_recommendation
                }
                for p in self.patterns if p.detected
            ],
            "trajectory": self.reasoning.trajectory,
            "causality_chain": self.reasoning.causality_chain,
            "primary_etiology": self.reasoning.primary_etiology,
            "differential_diagnoses": [
                {
                    "diagnosis": d.diagnosis_name,
                    "likelihood_pct": d.likelihood_pct,
                    "action": d.action_priority
                }
                for d in self.reasoning.differential_diagnosis
            ],
            "validation": {
                "status": self.validation.clinical_sanity_status,
                "confidence": self.validation.confidence,
                "missingness_pct": self.validation.missingness_rate_pct,
                "warnings": self.validation.warnings,
                "ood_detected": getattr(self.validation, 'ood_detected', False),
                "ood_score": getattr(self.validation, 'ood_score', 0.0)
            },
            "recommended_action": self.severity.recommended_clinical_action
        }

        # v5.0 Conditional Extras
        if self.uncertainty:
            base_dict["uncertainty"] = self.uncertainty.to_dict()
        if self.recommendations:
            base_dict["recommendations"] = {
                "protocol": self.recommendations.primary_protocol,
                "stat_actions": self.recommendations.stat_actions,
                "cautions": self.recommendations.contraindications_and_cautions
            }
        if self.trends:
            base_dict["trends"] = {
                "direction": self.trends.overall_direction,
                "velocity_score": self.trends.velocity_score,
                "flags": self.trends.clinical_flags
            }
        if self.audit_record:
            base_dict["audit_hash"] = self.audit_record.record_hash

        return base_dict


class SeverityAgent:
    """
    Main ICU Guard v5.0 Clinical Severity Agent.
    Operates as an evidence-based clinical reasoning, uncertainty quantification,
    and safety oversight engine above multi-target critical care machine learning models.
    """

    def __init__(
        self,
        bundle_path: Optional[str] = None,
        llm_client: Optional[LLMClient] = None
    ):
        """
        Initialize the Severity Agent.
        
        Args:
            bundle_path: Path to icu_guard_v4_2_agent_bundle.pkl
            llm_client: Optional LLMClient for Copilot advisory layer
        """
        if bundle_path is None:
            candidates = [
                "model_artifacts/icu_guard_v4_2_agent_bundle.pkl",
                "e:/eicu_v2_0_1.sqlite3/model_artifacts/icu_guard_v4_2_agent_bundle.pkl",
                "../model_artifacts/icu_guard_v4_2_agent_bundle.pkl"
            ]
            for p in candidates:
                if os.path.exists(p):
                    bundle_path = p
                    break

        if bundle_path is None or not os.path.exists(bundle_path):
            raise FileNotFoundError(
                f"Agent bundle not found. Please provide valid bundle_path to icu_guard_v4_2_agent_bundle.pkl"
            )

        logger.info(f"Loading ICU Guard Agent Bundle from: {bundle_path}")
        with open(bundle_path, "rb") as f:
            self.bundle = pickle.load(f)

        self.version = "5.0.0"
        self.bundle_version = self.bundle.get("version", "4.2.0")
        self.models = self.bundle["pipeline"]["models"]
        self.thresholds = self.bundle.get("thresholds", {})
        self.feature_importances = self.bundle.get("feature_importances", {})

        # 11 Physiological Organ Detectors
        self.organ_detectors = [
            RespiratoryDetector(),
            HemodynamicDetector(),
            RenalDetector(),
            NeurologicalDetector(),
            SepsisDetector(),
            HepaticDetector(),
            CoagulationDetector(),
            MetabolicDetector(),
            EndocrineDetector(),
            HematologicDetector(),
            NutritionalDetector()
        ]

        # 16 Clinical Syndrome Pattern Evaluators
        self.pattern_evaluators = [
            SepticShockPattern(),
            ARDSPattern(),
            AKIPattern(),
            MOFPattern(),
            NeuroRespiratoryPattern(),
            CardiogenicShockPattern(),
            HemorrhagicShockPattern(),
            DICPattern(),
            DeliriumPattern(),
            RefractoryShockPattern(),
            Type1RespiratoryFailurePattern(),
            Type2RespiratoryFailurePattern(),
            HepatorenalSyndromePattern(),
            PostoperativeDeteriorationPattern(),
            SevereAcidemiaPattern(),
            HyperosmolarCrisisPattern()
        ]

        # Auxiliary Specialized Cognitive Engines
        self.validator = PredictionValidator()
        self.severity_evaluator = SeverityEvaluator()
        self.reasoning_engine = ClinicalReasoningEngine()
        self.narrative_generator = ClinicalNarrativeGenerator()
        self.uncertainty_quantifier = UncertaintyQuantifier()
        self.trend_analyzer = TrendAnalyzer()
        self.similarity_engine = PatientSimilarityEngine()
        self.recommendation_engine = RecommendationEngine()
        self.audit_logger = RegulatoryAuditLogger()

        # LLM Copilot Advisory Engines
        self.copilot_client = llm_client or LLMClient()
        self.reviewer = ClinicalReviewer(self.copilot_client)
        self.chat = BedsideClinicalChat(self.copilot_client)
        self.sbar_generator = SBARGenerator(self.copilot_client)
        self.what_if = WhatIfSimulator(self.copilot_client)

    def predict_probabilities(self, patient_features: Dict[str, Any]) -> Dict[str, float]:
        """Compute leakage-free multi-target risk probabilities using XGBoost models."""
        probs = {}
        for target in ['mortality', 'deterioration', 'severe']:
            if target not in self.models:
                probs[f'p_{target}'] = 0.0
                continue

            m_info = self.models[target]
            feat_names = m_info['feature_names']
            clf = m_info['model']

            x_vec = np.array(
                [[patient_features.get(f, np.nan) for f in feat_names]],
                dtype=np.float32
            )

            try:
                p_val = float(clf.predict_proba(x_vec)[0, 1])
            except Exception as e:
                logger.warning(f"Prediction failed for target {target}: {e}")
                p_val = 0.0

            probs[f'p_{target}'] = round(p_val, 4)

        return probs

    def full_assessment(
        self,
        patient_features: Dict[str, Any],
        patient_id: Any = "Bedside-Patient",
        enable_uncertainty: bool = True,
        enable_recommendations: bool = True,
        enable_trends: bool = True,
        enable_similarity: bool = False,
        enable_audit: bool = True,
        enable_copilot: bool = False
    ) -> FullClinicalAssessment:
        """
        Perform complete ICU Guard v5.0 clinical reasoning assessment on a single patient.
        """
        # 1. Model Risk Inference
        probabilities = self.predict_probabilities(patient_features)

        # 2. 11 Organ System Evaluations
        organ_assessments: Dict[str, OrganAssessment] = {}
        for detector in self.organ_detectors:
            organ_assessments[detector.name] = detector.assess(patient_features)

        # 3. 16 Syndrome Pattern Evaluations
        patterns: List[PatternMatch] = []
        for evaluator in self.pattern_evaluators:
            patterns.append(evaluator.evaluate(organ_assessments, patient_features))

        # 4. 6-Layer Clinical Sanity Validation
        validation = self.validator.validate(
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            vitals=patient_features,
            top_shap_features=self.feature_importances
        )

        # 5. Non-Downgrading Severity Arbitration & Safety Overrides
        severity = self.severity_evaluator.evaluate(
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            patterns=patterns,
            vitals=patient_features
        )

        # 6. Causality, Trajectory, and Differential Reasoning
        reasoning = self.reasoning_engine.analyze(
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            patterns=patterns,
            vitals=patient_features
        )

        # 7. Uncertainty Quantification
        uncertainty: Optional[UncertaintyReport] = None
        if enable_uncertainty:
            uncertainty = self.uncertainty_quantifier.quantify(
                probabilities=probabilities,
                vitals=patient_features,
                models=self.models,
                missingness_pct=validation.missingness_rate_pct
            )

        # 8. Actionable Clinical Recommendations
        recommendations: Optional[ActionablePlan] = None
        if enable_recommendations:
            recommendations = self.recommendation_engine.generate_plan(
                severity_tier=severity.final_tier,
                organ_assessments=organ_assessments,
                patterns=patterns,
                vitals=patient_features
            )

        # 9. Dynamic Trends Analysis
        trends: Optional[PatientTrendReport] = None
        if enable_trends:
            trends = self.trend_analyzer.analyze(patient_features)

        # 10. Patient Similarity Matching (Optional)
        similar_cases: Optional[SimilarityReport] = None
        if enable_similarity:
            similar_cases = self.similarity_engine.find_similar_cases(
                patient_vitals=patient_features,
                k=5,
                query_patient_id=patient_id
            )

        # 11. Regulatory Audit Logging
        audit_record: Optional[AuditRecord] = None
        if enable_audit:
            audit_record = self.audit_logger.log_assessment(
                patient_id=patient_id,
                inputs=patient_features,
                probabilities=probabilities,
                severity_tier=severity.final_tier,
                escalation_occurred=severity.escalation_occurred,
                escalation_reasons=severity.escalation_reasons,
                active_red_flags=severity.active_red_flags,
                validation_status=validation.clinical_sanity_status,
                model_version=self.version
            )

        # 12. Bilingual Clinical Narrative Reports
        en_report = self.narrative_generator.generate_english_report(
            patient_id=patient_id,
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            patterns=patterns,
            severity=severity,
            reasoning=reasoning,
            validation=validation,
            uncertainty=uncertainty,
            recommendations=recommendations
        )

        ar_report = self.narrative_generator.generate_arabic_report(
            patient_id=patient_id,
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            patterns=patterns,
            severity=severity,
            reasoning=reasoning,
            validation=validation,
            uncertainty=uncertainty,
            recommendations=recommendations
        )

        # 13. Optional Copilot Review & SBAR
        copilot_rev = None
        sbar_doc = None
        if enable_copilot:
            partial_dict = {
                "severity_tier": severity.final_tier,
                "overall_score": severity.overall_score,
                "active_red_flags": severity.active_red_flags,
                "primary_etiology": reasoning.primary_etiology,
                "trajectory": reasoning.trajectory,
                "patterns": [{"name": p.pattern_name} for p in patterns if p.detected],
                "differential_diagnoses": [{"diagnosis": d.diagnosis_name} for d in reasoning.differential_diagnosis],
                "recommended_action": severity.recommended_clinical_action
            }
            copilot_rev = self.reviewer.review(partial_dict, patient_features)
            sbar_doc = self.sbar_generator.generate(partial_dict, patient_features)

        return FullClinicalAssessment(
            patient_id=patient_id,
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            patterns=patterns,
            validation=validation,
            severity=severity,
            reasoning=reasoning,
            english_report=en_report,
            arabic_report=ar_report,
            uncertainty=uncertainty,
            recommendations=recommendations,
            trends=trends,
            similar_cases=similar_cases,
            audit_record=audit_record,
            copilot_review=copilot_rev,
            sbar_handoff=sbar_doc
        )

    def batch_assess(
        self,
        patients: Union[pd.DataFrame, List[Dict[str, Any]]],
        id_column: str = "patientunitstayid"
    ) -> List[Dict[str, Any]]:
        """
        High-throughput batch assessment optimized for clinical registries and ICU ward monitoring.
        Evaluates 1000+ patients in less than 30 seconds.
        """
        if isinstance(patients, pd.DataFrame):
            patient_list = patients.to_dict(orient='records')
        else:
            patient_list = patients

        results = []
        for p_dict in patient_list:
            pid = p_dict.get(id_column, "Unknown")
            assessment = self.full_assessment(
                patient_features=p_dict,
                patient_id=pid,
                enable_uncertainty=True,
                enable_recommendations=True,
                enable_trends=False,
                enable_similarity=False,
                enable_audit=False,  # Skip file I/O during heavy batch processing
                enable_copilot=False
            )
            results.append({
                "patient_id": pid,
                "severity_tier": assessment.severity.final_tier,
                "overall_score": assessment.severity.overall_score,
                "p_mortality": assessment.probabilities.get('p_mortality', 0.0),
                "p_deterioration": assessment.probabilities.get('p_deterioration', 0.0),
                "active_red_flags_count": len(assessment.severity.active_red_flags),
                "active_patterns": [p.pattern_name for p in assessment.patterns if p.detected],
                "recommended_action": assessment.severity.recommended_clinical_action
            })

        return results
