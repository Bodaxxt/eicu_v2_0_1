"""
ICU Guard v5.0 — Dashboard Configuration
Defines server, theme, file paths, and runtime settings.
"""

import os
from pathlib import Path
from dataclasses import dataclass

# Project Root Resolution
BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
ASSETS_DIR = DASHBOARD_DIR / "assets"
CACHE_DIR = DASHBOARD_DIR / "cache"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)


@dataclass(frozen=True)
class DashboardConfig:
    """Central configuration for NiceGUI dashboard."""
    # App Identity
    APP_NAME: str = "ICU Guard v5.0"
    APP_TITLE: str = "ICU Guard v5.0 — Clinical Decision Support Platform"
    APP_VERSION: str = "5.0.0"
    SUBTITLE: str = "Real-Time Multi-Target Acuity Assessment & Clinical Advisory"

    # Server Networking
    HOST: str = os.getenv("ICU_GUARD_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("ICU_GUARD_PORT", "8080"))
    RELOAD: bool = False
    DARK_MODE: bool = True

    # Cohort & Model Paths
    CACHE_DIR: Path = CACHE_DIR
    ASSETS_DIR: Path = ASSETS_DIR
    COHORT_CSV: Path = BASE_DIR / "multilabel_cohort.csv"
    BUNDLE_PKL: Path = BASE_DIR / "model_artifacts" / "icu_guard_v4_2_agent_bundle.pkl"
    CACHE_FILE: Path = CACHE_DIR / "cohort_with_tiers_cache.parquet"
    CACHE_PICKLE: Path = CACHE_DIR / "cohort_with_tiers_cache.pkl"

    # UI Pagination & Limits
    ROWS_PER_PAGE: int = 50
    PAGINATION_OPTIONS = [25, 50, 100, 200]


config = DashboardConfig()
