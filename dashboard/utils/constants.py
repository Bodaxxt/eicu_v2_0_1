"""
ICU Guard v5.0 — Dashboard Constants & Design Palette.
Stage 1: Clinical Triage Tier Definitions and Styling Codes.
"""

from typing import Dict, Any

# Primary Clinical Severity Tiers
TIER_CRITICAL = "CRITICAL"
TIER_HIGH = "HIGH"
TIER_MODERATE = "MODERATE"
TIER_STABLE = "STABLE"

ALL_TIERS = [TIER_CRITICAL, TIER_HIGH, TIER_MODERATE, TIER_STABLE]

# Exact Clinical Triage Color Palette as Specified
TIER_COLORS: Dict[str, str] = {
    TIER_CRITICAL: "#DC143C",   # Crimson / Emergency Red
    TIER_HIGH: "#FF8C00",       # Dark Orange / Urgent
    TIER_MODERATE: "#FFD700",   # Golden Yellow / Guarded
    TIER_STABLE: "#32CD32",     # Lime Green / Low Risk
}

# Dark Mode Surface & Accent Colors
THEME_BG = "#0f172a"            # Slate 900
THEME_CARD_BG = "#1e293b"       # Slate 800
THEME_SURFACE = "#334155"       # Slate 700
THEME_TEXT_PRIMARY = "#f8fafc"  # Slate 50
THEME_TEXT_MUTED = "#94a3b8"    # Slate 400
THEME_BORDER = "rgba(255, 255, 255, 0.08)"
THEME_ACCENT_BLUE = "#3b82f6"   # Electric Blue
THEME_ACCENT_CYAN = "#06b6d4"   # Cyan / Telemetry

# Table Column Definitions for NiceGUI QTable
PATIENT_TABLE_COLUMNS = [
    {
        "name": "id",
        "label": "PATIENT ID",
        "field": "id",
        "required": True,
        "align": "left",
        "sortable": True,
    },
    {
        "name": "age",
        "label": "AGE",
        "field": "age",
        "align": "center",
        "sortable": True,
    },
    {
        "name": "gender",
        "label": "GENDER",
        "field": "gender",
        "align": "center",
        "sortable": True,
    },
    {
        "name": "apache",
        "label": "APACHE IV",
        "field": "apache",
        "align": "center",
        "sortable": True,
    },
    {
        "name": "tier",
        "label": "SEVERITY TIER",
        "field": "tier",
        "align": "center",
        "sortable": True,
    },
    {
        "name": "p_deterioration",
        "label": "DET. RISK",
        "field": "p_deterioration_pct",
        "align": "center",
        "sortable": True,
    },
    {
        "name": "actions",
        "label": "ACTIONS",
        "field": "actions",
        "align": "center",
        "sortable": False,
    },
]
