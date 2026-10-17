# 📝 ICU Guard — Changelog

All notable changes to the ICU Guard clinical intelligence platform are documented in this file.

---

## [5.1.0] — 2026-10-15 (NiceGUI Clinical Dashboard & Online Copilot)

### 🌟 Major Highlights
- **Online AI Chat & Secure API Keys:**
  - Added multi-provider remote LLM client (`OpenAI`, `Azure OpenAI`, `Gemini`, `Ollama`) with automatic fallback to Pure Python offline mode.
  - Zero PHI leakage enforced via regex/rule-based redaction prior to any network dispatch.
  - Environment variable isolation (`.env` ignored in Git, `.env.example` template provided).
- **Phase 1: Patient Selection Registry (`/` and `/patient_selection`):**
  - High-performance reactive table supporting 1,706 eICU patient cohort with pagination, search, and triaging filters.
  - Direct navigation to Live Monitor and Final Assessment views.
- **Phase 2: Live Monitor & Telemetry Streaming (`/live_monitor` and `/simulation`):**
  - Real-time physiological telemetry streamer with playback controls (1x, 2x, 5x speed, pause/resume).
  - Dynamic vital signs cards with SVG sparklines and color-coded alert boundaries.
  - Real-time AI analysis panel with escalation notifications and active red flags.
- **Phase 3: Final Assessment, SBAR, Chat, and PDF Export (`/final_assessment`):**
  - Multi-tier Triage Header (STABLE / MODERATE / HIGH / CRITICAL) with active red flag banners.
  - Tri-gauge Plotly risk meters (Mortality, Deterioration, Severe Sepsis/Septic Shock).
  - 11-system physiological organ failure cards with 0–3 grading.
  - 16 syndrome pattern evaluation cards with confidence scores.
  - Prioritized Actionable Care Bundles with STAT urgency indicators.
  - Bilingual Clinical Narrative viewer with English and Arabic tabs.
  - Conformal Uncertainty Quantification dashboard with reliability tiers and 90% confidence intervals.
  - Interactive SBAR clinical handoff modal with one-click clipboard copy.
  - Bedside Clinical Chat interface with async streaming and offline/online fallback.
  - ReportLab PDF export engine generating downloadable, publication-grade clinical summaries.
- **Testing:** 164/164 automated unit, integration, and regression tests passing.

---

## [5.0.0] — 2026-10-15 (The Ultimate Clinical AI Agent Release)

### 🌟 Major Highlights
- **Architecture Invariant:** Established strict boundary where Pure Python logic is the sole **Decision Maker**, and the LLM is an **Advisory Copilot** with zero PHI leakage and 100% offline fallback.
- **Detector Expansion (5 $\to$ 11 Systems):** Added Hepatic, Coagulation, Metabolic, Endocrine, Hematologic, and Nutritional organ detectors with 0–3 injury grading and guideline actions.
- **Pattern Expansion (5 $\to$ 16 Syndromes):** Added Cardiogenic Shock, Hemorrhagic Shock, DIC, Delirium, Refractory Shock, Type 1 Resp Failure, Type 2 Resp Failure, Hepatorenal Syndrome, Post-Op Deterioration, Severe Acidemia, and Hyperosmolar Crisis.
- **6-Layer Clinical Sanity & OOD Validator:** Added Out-of-Distribution (OOD) covariate distance tracking, temporal plausibility, and subsystem-level missingness auditing.
- **Directed Causal Graphs & Counterfactuals:** Upgraded reasoning engine with multi-hypothesis differential tracking, 12h trajectory projections, and resuscitation counterfactual simulations.
- **Conformal Uncertainty Quantification:** Conformal prediction intervals with 90% finite-sample coverage guarantees, vectorized bootstrap confidence bounds (< 1ms overhead), and Epistemic vs Aleatoric uncertainty decomposition.
- **Bedside Clinical Tools:**
  - `trends.py`: Autonomic vital volatility and velocity scoring.
  - `similarity.py`: Nearest-neighbor patient case retrieval against the 1,706-patient eICU cohort.
  - `recommendations.py`: Actionable evidence-based care bundles (Surviving Sepsis Hour-1, KDIGO AKI, Berlin ARDSNet, Massive Transfusion).
  - `audit.py`: Cryptographic SHA-256 hash-chained regulatory audit ledger with chain verification.
- **Advisory LLM Copilot (`llm_copilot/`):**
  - `safety.py`: Regex/rule-based HIPAA PHI scrubbing and non-autonomous watermarking.
  - `client.py`: Multi-backend client with seamless offline deterministic fallback.
  - `reviewer.py`: Automated intensivist second-opinion review.
  - `chat.py`: Bedside clinical Q&A interface.
  - `sbar.py`: Standardized SBAR shift handoff document generator.
  - `what_if.py`: Counterfactual intervention simulator.
- **Bilingual Clinical Reporting:** Automated English and Arabic narrative report generation.
- **Performance Benchmarks Met:**
  - Assessment Latency: **17.77 ms** (Requirement: $< 100\text{ ms}$).
  - Batch Processing: **1,000 patients in 17.25s** (Requirement: $< 60\text{ s}$).
  - Process Memory RSS: **194.5 MB** (Requirement: $< 500\text{ MB}$).
- **Testing:** 101/101 automated tests passing with zero failures.

---

### 🔬 Detailed Component Changes

#### Added
- `severity_agent/uncertainty.py`: `UncertaintyQuantifier` class implementing Conformal prediction, vectorized biological bootstrap, OOD scoring, and aleatoric/epistemic decomposition.
- `severity_agent/trends.py`: `TrendAnalyzer` class calculating autonomic volatility and range dynamics.
- `severity_agent/similarity.py`: `PatientSimilarityEngine` performing normalized Euclidean/Cosine nearest neighbor searches on `multilabel_cohort.csv`.
- `severity_agent/recommendations.py`: `RecommendationEngine` generating protocolized care bundles for septic shock, ARDS, AKI, and massive transfusion.
- `severity_agent/audit.py`: `RegulatoryAuditLogger` writing immutable SHA-256 hash-chained JSONL records.
- `severity_agent/llm_copilot/`: Complete subpackage containing safety PHI scrubber, offline client, clinical reviewer, chat, SBAR generator, and what-if simulator.
- `demo_v5.py`: Interactive demonstration script running single patient assessment, archetype triage, bedside Q&A, and 500-patient batch throughput.
- `ARCHITECTURE.md`: In-depth architecture specification.
- `CLINICAL_RATIONALE.md`: Comprehensive medical justification for all thresholds.
- Test suites:
  - `tests/test_detectors_v5.py`
  - `tests/test_patterns_v5.py`
  - `tests/test_uncertainty.py`
  - `tests/test_reasoning_v5.py`
  - `tests/test_clinical_tools.py`
  - `tests/test_llm_copilot.py`
  - `tests/test_integration_cohort.py`
  - `tests/test_performance.py`

#### Changed
- `severity_agent/config.py`: Expanded with `HEPATIC_CONFIG`, `COAGULATION_CONFIG`, `METABOLIC_CONFIG`, `ENDOCRINE_CONFIG`, `HEMATOLOGIC_CONFIG`, `NUTRITIONAL_CONFIG`, 16 `PATTERN_CONFIG` entries, `UNCERTAINTY_CONFIG`, and updated `ABSOLUTE_RED_FLAGS`.
- `severity_agent/detectors.py`: Implemented 6 new organ detectors (`HepaticDetector`, `CoagulationDetector`, `MetabolicDetector`, `EndocrineDetector`, `HematologicDetector`, `NutritionalDetector`) and added `suggested_action` to all detectors.
- `severity_agent/patterns.py`: Implemented 11 new syndrome pattern classes.
- `severity_agent/validator.py`: Upgraded to 6-layer audit with OOD metric and subsystem missingness rate breakdown.
- `severity_agent/severity.py`: Fixed multi-organ ratio (`total_organs = max(1, len(organ_assessments))`), expanded red flags (platelets <= 20, glucose <= 40, K >= 6.5, K <= 2.5).
- `severity_agent/reasoning.py`: Added directed causal graph construction, 12h trajectory projection, and multi-hypothesis differential diagnosis tracking.
- `severity_agent/narrative.py`: Expanded English and Arabic report templates to format all 11 organs, uncertainty intervals, and care recommendations.
- `severity_agent/agent.py`: Integrated all v5.0 sub-engines into `SeverityAgent`, adding `batch_assess` and optional copilot switches.
- `severity_agent/__init__.py`: Version bumped to `5.0.0` with clean module exports.

#### Fixed
- Fixed single-patient assessment latency bottleneck by vectorizing bootstrap biological perturbations into single XGBoost matrix inferences ($97\text{ ms} \to 17\text{ ms}$).
- Fixed multi-organ failure ratio calculation in severity arbitrator.
- Fixed Windows UTF-8 stdout encoding compatibility for Arabic narrative reports.
- Ensured regulatory audit ledger maintains continuous cryptographic chain across multiple process instances.

---

## [4.2.0] — Earlier Release

- Phase 0: Frozen XGBoost multi-target models (`mortality`, `deterioration`, `severe`).
- Phase 1: Severity Agent Core with 5 organ detectors (Respiratory, Hemodynamic, Renal, Neurological, Sepsis).
- 5 Clinical syndrome pattern matchers (Septic Shock, ARDS, AKI, MOF, Neuro-Respiratory).
- 4-layer validation, non-downgrading severity arbitration, basic reasoning, and bilingual narratives.
- 20 unit tests.
