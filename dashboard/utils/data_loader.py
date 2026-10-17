"""
ICU Guard v5.0 — High-Performance Cohort Data Loader & Caching Engine
Loads multilabel_cohort.csv, computes clinical severity tiers via SeverityAgent,
and persists cached results for millisecond UI loading.
"""

import os
import pickle
import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd

from dashboard.config import config
from dashboard.utils.constants import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    TIER_STABLE,
    ALL_TIERS,
)

logger = logging.getLogger("icu_guard.data_loader")
logging.basicConfig(level=logging.INFO)


class DataLoader:
    """Manages cohort dataset, clinical tier calculation, and disk caching."""

    def __init__(self):
        self._df: Optional[pd.DataFrame] = None
        self._patient_map: Dict[str, Dict[str, Any]] = {}
        self._is_loaded: bool = False

    def load_cohort(self, force_recompute: bool = False) -> pd.DataFrame:
        """
        Loads the 1,706 patient cohort with precomputed clinical tiers.
        Uses cached parquet/pickle if available; otherwise computes via SeverityAgent.
        """
        if self._df is not None and not force_recompute:
            return self._df

        # 1. Try Loading from Disk Cache (Pickle primary for Python 3.13 stability)
        if not force_recompute:
            if config.CACHE_PICKLE.exists():
                try:
                    logger.info(f"Loading cached cohort from: {config.CACHE_PICKLE}")
                    with open(config.CACHE_PICKLE, "rb") as f:
                        df = pickle.load(f)
                    self._process_loaded_df(df)
                    return self._df
                except Exception as pe:
                    logger.warning(f"Pickle cache load failed: {pe}. Trying parquet...")

            if config.CACHE_FILE.exists():
                try:
                    logger.info(f"Loading cached cohort from: {config.CACHE_FILE}")
                    df = pd.read_parquet(config.CACHE_FILE)
                    self._process_loaded_df(df)
                    return self._df
                except Exception as e:
                    logger.warning(f"Parquet cache load failed: {e}. Recomputing...")

        # 2. Compute Tiers from Raw Cohort CSV
        logger.info(f"Loading raw cohort from: {config.COHORT_CSV}")
        if not config.COHORT_CSV.exists():
            raise FileNotFoundError(f"Cohort CSV not found at: {config.COHORT_CSV}")

        raw_df = pd.read_csv(config.COHORT_CSV)
        logger.info(f"Cohort loaded: {raw_df.shape[0]} patients, {raw_df.shape[1]} features.")

        # Import SeverityAgent to compute deterministic clinical tiers
        from severity_agent.agent import SeverityAgent

        agent = SeverityAgent(bundle_path=str(config.BUNDLE_PKL))
        logger.info("Computing clinical severity tiers across cohort via SeverityAgent.batch_assess()...")
        
        batch_results = agent.batch_assess(raw_df, id_column="patientunitstayid")
        
        # Merge batch assessment results into DataFrame
        assess_df = pd.DataFrame(batch_results)
        
        # Merge on patientunitstayid == patient_id
        df = raw_df.copy()
        df["patient_id_str"] = df["patientunitstayid"].astype(str)
        assess_df["patient_id_str"] = assess_df["patient_id"].astype(str)
        
        merged_df = df.merge(
            assess_df[
                [
                    "patient_id_str",
                    "severity_tier",
                    "overall_score",
                    "p_mortality",
                    "p_deterioration",
                    "active_red_flags_count",
                    "recommended_action",
                ]
            ],
            on="patient_id_str",
            how="left",
        )
        
        # Fallback if any missing
        merged_df["severity_tier"] = merged_df["severity_tier"].fillna(TIER_MODERATE)

        # Cache to disk for instant future loads
        try:
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # Try parquet first, with pickle fallback
            try:
                # Convert active patterns or list cols if any
                merged_df.to_parquet(config.CACHE_FILE, index=False)
                logger.info(f"Saved parquet cache: {config.CACHE_FILE}")
            except Exception as pe:
                logger.warning(f"Could not save parquet ({pe}), saving pickle...")
            
            with open(config.CACHE_PICKLE, "wb") as pf:
                pickle.dump(merged_df, pf, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"Saved pickle cache: {config.CACHE_PICKLE}")
        except Exception as ce:
            logger.error(f"Failed to cache cohort data: {ce}")

        self._process_loaded_df(merged_df)
        return self._df

    def _process_loaded_df(self, df: pd.DataFrame) -> None:
        """Adds normalized UI presentation columns and indexes by patient ID."""
        df = df.copy()

        # Display ID
        if "patientunitstayid" in df.columns:
            df["id"] = df["patientunitstayid"].astype(str)
        elif "patient_id" in df.columns:
            df["id"] = df["patient_id"].astype(str)
        else:
            df["id"] = df.index.astype(str)

        # Standardize Age
        if "age_clean" in df.columns:
            df["age"] = df["age_clean"].apply(
                lambda v: f"{int(v)}" if pd.notna(v) and str(v) != "> 89" else str(v)
            )
        elif "age" in df.columns:
            df["age"] = df["age"].fillna("N/A").astype(str)
        else:
            df["age"] = "N/A"

        # Standardize Gender
        if "gender" in df.columns:
            df["gender"] = df["gender"].fillna("Unknown").astype(str).str.capitalize()
        else:
            df["gender"] = "Unknown"

        # Standardize APACHE IV Score
        if "apachescore" in df.columns:
            df["apache"] = df["apachescore"].apply(
                lambda v: f"{int(v)}" if pd.notna(v) and v > 0 else "N/A"
            )
        else:
            df["apache"] = "N/A"

        # Severity Tier
        if "severity_tier" in df.columns:
            df["tier"] = df["severity_tier"].astype(str)
        else:
            df["tier"] = TIER_MODERATE

        # Formatted Probabilities
        if "p_deterioration" in df.columns:
            df["p_deterioration_pct"] = df["p_deterioration"].apply(
                lambda v: f"{v * 100:.1f}%" if pd.notna(v) else "0.0%"
            )
        else:
            df["p_deterioration_pct"] = "—"

        if "p_mortality" in df.columns:
            df["p_mortality_pct"] = df["p_mortality"].apply(
                lambda v: f"{v * 100:.1f}%" if pd.notna(v) else "0.0%"
            )
        else:
            df["p_mortality_pct"] = "—"

        self._df = df

        # Index patient dictionary for O(1) instant bedside lookup
        records = df.to_dict(orient="records")
        self._patient_map = {str(r["id"]): r for r in records}
        self._is_loaded = True
        logger.info(f"Processed and indexed {len(self._patient_map)} clinical patients.")

    def get_patient(self, patient_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Instant O(1) lookup of a patient record by ID."""
        if not self._is_loaded:
            self.load_cohort()
        return self._patient_map.get(str(patient_id))

    def get_patient_row(self, patient_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Return the full raw feature row for a patient, suitable for SeverityAgent.full_assessment().

        This returns all 154 cohort columns without the normalised UI columns so the
        agent receives a clean numeric feature dict.

        Args:
            patient_id: Patient identifier string or int.

        Returns:
            Dict with all raw cohort features, or ``None`` if patient not found.
        """
        if not self._is_loaded:
            self.load_cohort()
        if self._df is None:
            return None
        pid_str = str(patient_id)
        mask = self._df["id"] == pid_str
        if not mask.any():
            return None
        row = self._df[mask].iloc[0]
        return row.to_dict()

    def get_random_patient(self) -> Dict[str, Any]:
        """Returns a random patient from the cohort."""
        if not self._is_loaded:
            self.load_cohort()
        import random
        return random.choice(list(self._patient_map.values()))

    def get_summary_stats(self) -> Dict[str, Any]:
        """Computes summary statistics for header dashboard KPI cards."""
        if not self._is_loaded:
            self.load_cohort()

        tier_counts = self._df["tier"].value_counts().to_dict()
        total_patients = len(self._df)

        return {
            "total_patients": total_patients,
            "critical_count": tier_counts.get(TIER_CRITICAL, 0),
            "high_count": tier_counts.get(TIER_HIGH, 0),
            "moderate_count": tier_counts.get(TIER_MODERATE, 0),
            "stable_count": tier_counts.get(TIER_STABLE, 0),
            "critical_pct": (tier_counts.get(TIER_CRITICAL, 0) / max(total_patients, 1)) * 100,
        }

    def get_filtered_records(
        self,
        tier_filter: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filters patient records by clinical tier and search term."""
        if not self._is_loaded:
            self.load_cohort()

        filtered_df = self._df

        if tier_filter and tier_filter.upper() != "ALL":
            filtered_df = filtered_df[filtered_df["tier"] == tier_filter.upper()]

        if search_query and search_query.strip():
            query = search_query.strip().lower()
            filtered_df = filtered_df[
                filtered_df["id"].str.lower().str.contains(query)
                | filtered_df["gender"].str.lower().str.contains(query)
                | filtered_df["age"].str.lower().str.contains(query)
            ]

        return filtered_df.to_dict(orient="records")


# Global Singleton Instance
_data_loader_instance: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    """Singleton access to DataLoader instance."""
    global _data_loader_instance
    if _data_loader_instance is None:
        _data_loader_instance = DataLoader()
    return _data_loader_instance
