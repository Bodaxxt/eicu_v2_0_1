"""
ICU Guard v5.0 — Dashboard Foundation & Patient Selection Tests
Tests data loading, tier computation, caching, filtering, search, and constants.
"""

import pytest
import pandas as pd
from dashboard.config import config
from dashboard.utils.constants import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    TIER_STABLE,
    ALL_TIERS,
    TIER_COLORS,
    PATIENT_TABLE_COLUMNS,
)
from dashboard.utils.data_loader import get_data_loader


def test_dashboard_constants_and_color_palette():
    """Verify tier color codes match required clinical guidelines."""
    assert TIER_COLORS[TIER_CRITICAL] == "#DC143C"
    assert TIER_COLORS[TIER_HIGH] == "#FF8C00"
    assert TIER_COLORS[TIER_MODERATE] == "#FFD700"
    assert TIER_COLORS[TIER_STABLE] == "#32CD32"

    assert len(ALL_TIERS) == 4
    col_fields = [c["field"] for c in PATIENT_TABLE_COLUMNS]
    assert "id" in col_fields
    assert "age" in col_fields
    assert "gender" in col_fields
    assert "apache" in col_fields
    assert "tier" in col_fields
    assert "actions" in col_fields


def test_data_loader_cohort_size_and_schema():
    """Verify data loader loads all 1,706 cohort patients with proper columns."""
    loader = get_data_loader()
    df = loader.load_cohort()
    assert len(df) == 1706
    assert "id" in df.columns
    assert "tier" in df.columns
    assert "p_deterioration" in df.columns
    assert "p_mortality" in df.columns


def test_data_loader_summary_stats():
    """Verify KPI summary stats calculation."""
    loader = get_data_loader()
    stats = loader.get_summary_stats()
    assert stats["total_patients"] == 1706
    assert stats["critical_count"] > 0
    assert stats["critical_pct"] > 0
    assert (
        stats["critical_count"]
        + stats["high_count"]
        + stats["moderate_count"]
        + stats["stable_count"]
        == 1706
    )


def test_data_loader_filtering_by_tier():
    """Verify filtering patients by clinical triage tier."""
    loader = get_data_loader()

    for tier in ALL_TIERS:
        filtered = loader.get_filtered_records(tier_filter=tier)
        assert len(filtered) > 0
        for patient in filtered:
            assert patient["tier"] == tier

    # Filter with ALL
    all_recs = loader.get_filtered_records(tier_filter="ALL")
    assert len(all_recs) == 1706


def test_data_loader_search_by_id():
    """Verify search filter by patient unit stay ID."""
    loader = get_data_loader()
    random_pt = loader.get_random_patient()
    target_id = random_pt["id"]

    results = loader.get_filtered_records(search_query=target_id)
    assert len(results) >= 1
    matched = [r for r in results if r["id"] == target_id]
    assert len(matched) == 1


def test_data_loader_instant_patient_lookup():
    """Verify O(1) instant dictionary lookup by ID."""
    loader = get_data_loader()
    random_pt = loader.get_random_patient()
    fetched = loader.get_patient(random_pt["id"])
    assert fetched is not None
    assert fetched["id"] == random_pt["id"]
    assert fetched["tier"] == random_pt["tier"]
