"""
ICU Guard v5.0 — Patient Case Similarity & Outcome Retrieval Engine
===================================================================
Identifies nearest neighbor clinical presentation matches from historical ICU cohorts:
1. Multi-Dimensional Clinical Presentation Vectorization
2. Cosine & Normalized Euclidean Distance Matching
3. Empirical Historical Outcome Aggregation (True Deterioration & Mortality in Similar Cohort)
4. Case-Based Clinical Precedent Retrieval for Intensivists
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import os
import math
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class SimilarCase:
    """Historical patient match retrieved from critical care cohort."""
    patient_id: Any
    similarity_score: float         # 0.0 to 1.0 (1.0 = identical presentation)
    age: Optional[float]
    unit_type: str
    mortality_outcome: int          # 0: Survived, 1: Died
    deterioration_outcome: int      # 0: Stable, 1: Deteriorated
    severe_outcome: int             # 0: Non-severe, 1: Severe
    key_features_summary: str


@dataclass
class SimilarityReport:
    """Cohort case retrieval analysis."""
    query_patient_id: Any
    top_matches: List[SimilarCase]
    cohort_deterioration_rate_pct: float
    cohort_mortality_rate_pct: float
    summary_insight: str


class PatientSimilarityEngine:
    """Retrieves top-k clinically similar historical cases from eICU cohort."""

    CORE_SIMILARITY_FEATURES = [
        'heartrate_mean', 'meanbp_min', 'respiration_max', 'sao2_min',
        'creatinine_max', 'bun_max', 'lactate_max', 'gcs_min', 'platelets_min', 'age_clean'
    ]

    def __init__(self, cohort_path: Optional[str] = None):
        self.cohort_path = cohort_path
        self._df: Optional[pd.DataFrame] = None
        self._feature_matrix: Optional[np.ndarray] = None
        self._means: Optional[np.ndarray] = None
        self._stds: Optional[np.ndarray] = None
        self._valid_rows: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is not None:
            return

        if self.cohort_path is None:
            candidates = [
                "multilabel_cohort.csv",
                "e:/eicu_v2_0_1.sqlite3/multilabel_cohort.csv",
                "../multilabel_cohort.csv"
            ]
            for c in candidates:
                if os.path.exists(c):
                    self.cohort_path = c
                    break

        if self.cohort_path and os.path.exists(self.cohort_path):
            try:
                self._df = pd.read_csv(self.cohort_path)
                # Extract and normalize core feature matrix
                feat_cols = [c for c in self.CORE_SIMILARITY_FEATURES if c in self._df.columns]
                sub = self._df[feat_cols].copy()
                
                # Compute reference stats for z-score normalization
                self._means = sub.mean().values
                self._stds = sub.std().replace(0, 1.0).values
                # Impute missing with mean for vectorized distance computation
                sub_filled = sub.fillna(sub.mean())
                self._feature_matrix = (sub_filled.values - self._means) / self._stds
                self._valid_rows = self._df
            except Exception as e:
                logger.warning(f"Could not load cohort for similarity engine: {e}")

    def find_similar_cases(
        self,
        patient_vitals: Dict[str, Any],
        k: int = 5,
        query_patient_id: Any = "Current-Patient"
    ) -> SimilarityReport:
        """Find the top-k most similar patients in the eICU database."""
        self._ensure_loaded()

        if self._feature_matrix is None or self._valid_rows is None:
            return SimilarityReport(
                query_patient_id=query_patient_id,
                top_matches=[],
                cohort_deterioration_rate_pct=0.0,
                cohort_mortality_rate_pct=0.0,
                summary_insight="Cohort dataset not loaded; similarity matching unavailable."
            )

        # Build query vector
        feat_cols = [c for c in self.CORE_SIMILARITY_FEATURES if c in self._valid_rows.columns]
        q_vals = []
        for c in feat_cols:
            v = patient_vitals.get(c)
            try:
                f_v = float(v) if v is not None and not math.isnan(float(v)) else np.nan
            except:
                f_v = np.nan
            q_vals.append(f_v)

        q_arr = np.array(q_vals)
        # Impute missing query values with cohort means
        nan_mask = np.isnan(q_arr)
        q_arr[nan_mask] = self._means[nan_mask]
        q_norm = (q_arr - self._means) / self._stds

        # Calculate Cosine / Euclidean distance across patients
        diffs = self._feature_matrix - q_norm
        dists = np.linalg.norm(diffs, axis=1)

        # Get top-k indices
        top_indices = np.argsort(dists)[:k]

        matches: List[SimilarCase] = []
        for idx in top_indices:
            row = self._valid_rows.iloc[idx]
            dist = dists[idx]
            sim_score = max(0.0, min(1.0, 1.0 / (1.0 + (dist / 5.0))))
            
            # Format unit type
            unit_type = "ICU"
            for col in row.index:
                if col.startswith('unittype_') and row[col] == 1:
                    unit_type = col.replace('unittype_', '')
                    break

            pid = row.get('patientunitstayid', f"Patient-{idx}")
            mort = int(row.get('y_mortality', 0))
            det = int(row.get('y_deterioration', 0))
            sev = int(row.get('y_severe', 0))
            age = row.get('age_clean') or row.get('age')

            summary_str = f"MAP {row.get('meanbp_min', 'N/A'):.0f} | HR {row.get('heartrate_mean', 'N/A'):.0f} | Cr {row.get('creatinine_max', 'N/A'):.1f} | Lact {row.get('lactate_max', 'N/A'):.1f}"

            matches.append(SimilarCase(
                patient_id=pid,
                similarity_score=round(float(sim_score), 3),
                age=float(age) if age is not None and not math.isnan(float(age)) else None,
                unit_type=unit_type,
                mortality_outcome=mort,
                deterioration_outcome=det,
                severe_outcome=sev,
                key_features_summary=summary_str
            ))

        # Calculate empirical cohort statistics
        det_rate = (sum(m.deterioration_outcome for m in matches) / max(1, len(matches))) * 100.0
        mort_rate = (sum(m.mortality_outcome for m in matches) / max(1, len(matches))) * 100.0

        insight = (
            f"Retrieved {len(matches)} closest matching patients from eICU cohort. "
            f"Among historical precedents: {det_rate:.0f}% suffered acute deterioration within 12h, "
            f"and {mort_rate:.0f}% suffered in-hospital mortality."
        )

        return SimilarityReport(
            query_patient_id=query_patient_id,
            top_matches=matches,
            cohort_deterioration_rate_pct=round(det_rate, 1),
            cohort_mortality_rate_pct=round(mort_rate, 1),
            summary_insight=insight
        )
