"""
ICU Guard v5.0 — Clinical Decision Support & Reasoning Agent Package
====================================================================
Evidence-based multi-modal clinical reasoning, uncertainty quantification,
and safety oversight layer for ICU patient deterioration.

Modules:
- config: Evidence-based clinical thresholds and guidelines.
- detectors: 11 Physiological organ system detectors (Berlin, SSC, KDIGO, GCS, SOFA, ISTH, ADA, AABB).
- patterns: 16 Multi-system clinical syndrome patterns (Septic Shock, ARDS, AKI, MOF, Cardiogenic, Hemorrhagic, etc.).
- validator: 6-layer prediction sanity, temporal plausibility, and OOD checks.
- severity: Non-downgrading severity arbitration and absolute safety overrides.
- reasoning: Causal graphs, trajectory prediction, multi-hypothesis tracking, and counterfactuals.
- narrative: Structured bilingual clinical report generation (English & Arabic).
- uncertainty: Conformal intervals, bootstrap sampling, and epistemic/aleatoric uncertainty.
- trends: Dynamic velocity, rate of change, and autonomic instability analysis.
- similarity: Historical cohort case retrieval and empirical outcome matching.
- recommendations: Actionable clinical bundles (SSC Hour-1, KDIGO AKI, ARDSNet, Transfusion MTP).
- audit: FDA SaMD / EU MDR-compliant cryptographically verifiable hash-chained audit ledger.
- llm_copilot: Optional advisory second-opinion reviewer, SBAR handoff, chat, and what-if simulation.
- agent: Main SeverityAgent interface.
"""

from severity_agent.agent import SeverityAgent, FullClinicalAssessment
from severity_agent.detectors import (
    OrganAssessment,
    BaseOrganDetector,
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
    BasePattern,
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
from severity_agent.reasoning import ClinicalReasoningEngine, ClinicalReasoningReport, DifferentialCandidate
from severity_agent.narrative import ClinicalNarrativeGenerator
from severity_agent.uncertainty import UncertaintyQuantifier, UncertaintyReport, TargetUncertainty
from severity_agent.trends import TrendAnalyzer, PatientTrendReport, VariableTrend
from severity_agent.similarity import PatientSimilarityEngine, SimilarityReport, SimilarCase
from severity_agent.recommendations import RecommendationEngine, ActionablePlan, ClinicalActionItem
from severity_agent.audit import RegulatoryAuditLogger, AuditRecord
from severity_agent.llm_copilot import (
    ClinicalReviewer,
    BedsideClinicalChat,
    SBARGenerator,
    WhatIfSimulator,
    LLMClient,
    PHIScrubber,
    stamp_advisory
)

__version__ = "5.0.0"

__all__ = [
    # Core Agent
    "SeverityAgent",
    "FullClinicalAssessment",
    # Detectors
    "OrganAssessment",
    "BaseOrganDetector",
    "RespiratoryDetector",
    "HemodynamicDetector",
    "RenalDetector",
    "NeurologicalDetector",
    "SepsisDetector",
    "HepaticDetector",
    "CoagulationDetector",
    "MetabolicDetector",
    "EndocrineDetector",
    "HematologicDetector",
    "NutritionalDetector",
    # Patterns
    "PatternMatch",
    "BasePattern",
    "SepticShockPattern",
    "ARDSPattern",
    "AKIPattern",
    "MOFPattern",
    "NeuroRespiratoryPattern",
    "CardiogenicShockPattern",
    "HemorrhagicShockPattern",
    "DICPattern",
    "DeliriumPattern",
    "RefractoryShockPattern",
    "Type1RespiratoryFailurePattern",
    "Type2RespiratoryFailurePattern",
    "HepatorenalSyndromePattern",
    "PostoperativeDeteriorationPattern",
    "SevereAcidemiaPattern",
    "HyperosmolarCrisisPattern",
    # Reasoning & Severity & Validation
    "PredictionValidator",
    "ValidationReport",
    "SeverityEvaluator",
    "SeverityAssessment",
    "ClinicalReasoningEngine",
    "ClinicalReasoningReport",
    "DifferentialCandidate",
    "ClinicalNarrativeGenerator",
    # Advanced Tools
    "UncertaintyQuantifier",
    "UncertaintyReport",
    "TargetUncertainty",
    "TrendAnalyzer",
    "PatientTrendReport",
    "VariableTrend",
    "PatientSimilarityEngine",
    "SimilarityReport",
    "SimilarCase",
    "RecommendationEngine",
    "ActionablePlan",
    "ClinicalActionItem",
    "RegulatoryAuditLogger",
    "AuditRecord",
    # LLM Copilot
    "ClinicalReviewer",
    "BedsideClinicalChat",
    "SBARGenerator",
    "WhatIfSimulator",
    "LLMClient",
    "PHIScrubber",
    "stamp_advisory",
]
