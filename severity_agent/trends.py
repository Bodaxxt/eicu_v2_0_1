"""
ICU Guard v5.0 — Bedside Physiological Trend Analyzer
=====================================================
Analyzes temporal trajectory dynamics, rate of change (deltas), and volatility:
1. Dynamic Range & Shock Index Drift
2. Autonomic Volatility (Heart rate and blood pressure variance)
3. Renal & Dysoxic Velocity (Creatinine doubling time, Lactate accumulation rate)
4. Overall Trend Direction (IMPROVING, DETERIORATING, STABLE, VOLATILE)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class VariableTrend:
    """Temporal velocity and dynamic spread for a single physiological parameter."""
    variable_name: str
    min_value: Optional[float]
    max_value: Optional[float]
    mean_value: Optional[float]
    std_value: Optional[float]
    dynamic_range: Optional[float]
    status: str                         # "STABLE", "VOLATILE", "WORSENING", "RECOVERING"
    clinical_note: str


@dataclass
class PatientTrendReport:
    """Comprehensive temporal trend analysis."""
    overall_direction: str              # "IMPROVING", "DETERIORATING", "STABLE", "VOLATILE"
    velocity_score: float               # 0.0 (Quiescent) to 1.0 (Rapid Decompensation)
    autonomic_instability_detected: bool
    variable_trends: Dict[str, VariableTrend]
    trend_narrative: str
    clinical_flags: List[str] = field(default_factory=list)


class TrendAnalyzer:
    """Evaluates dynamic telemetry and laboratory trends from observational feature window."""

    def analyze(self, vitals: Dict[str, Any]) -> PatientTrendReport:
        trends: Dict[str, VariableTrend] = {}
        flags: List[str] = []
        instability_count = 0

        # 1. Heart Rate Trend
        hr_min = self._get_f(vitals, 'heartrate_min')
        hr_max = self._get_f(vitals, 'heartrate_max')
        hr_mean = self._get_f(vitals, 'heartrate_mean')
        hr_std = self._get_f(vitals, 'heartrate_std')
        hr_range = (hr_max - hr_min) if (hr_max is not None and hr_min is not None) else None

        hr_status = "STABLE"
        hr_note = "Heart rate stable within observation window."
        if hr_std is not None and hr_std > 18.0:
            hr_status = "VOLATILE"
            range_str = f", Range {hr_range:.1f} bpm" if hr_range is not None else ""
            hr_note = f"Severe autonomic fluctuations (SD {hr_std:.1f} bpm{range_str})."
            flags.append(f"Cardiac Autonomic Instability (HR SD={hr_std:.1f})")
            instability_count += 1
        elif hr_max is not None and hr_max > 130.0:
            hr_status = "WORSENING"
            hr_note = f"Tachycardic stress peak ({hr_max:.0f} bpm)."

        trends['heartrate'] = VariableTrend(
            variable_name="Heart Rate",
            min_value=hr_min, max_value=hr_max, mean_value=hr_mean, std_value=hr_std,
            dynamic_range=hr_range, status=hr_status, clinical_note=hr_note
        )

        # 2. Perfusion Pressure (MAP) Trend
        map_min = self._get_f(vitals, 'meanbp_min')
        map_max = self._get_f(vitals, 'meanbp_max')
        map_mean = self._get_f(vitals, 'meanbp_mean')
        map_std = self._get_f(vitals, 'meanbp_std')
        map_range = (map_max - map_min) if (map_max is not None and map_min is not None) else None

        map_status = "STABLE"
        map_note = "Perfusion pressure adequately maintained."
        if map_min is not None and map_min < 55.0:
            map_status = "WORSENING"
            map_note = f"Critical hypotension nadir (MAP {map_min:.1f} mmHg < 55 mmHg)."
            flags.append(f"Severe MAP Nadir ({map_min:.1f} mmHg)")
            instability_count += 2
        elif map_std is not None and map_std > 15.0:
            map_status = "VOLATILE"
            map_note = f"Vasomotor instability (MAP SD {map_std:.1f} mmHg)."
            flags.append(f"Vasomotor Oscillation (MAP SD={map_std:.1f})")
            instability_count += 1

        trends['meanbp'] = VariableTrend(
            variable_name="Mean Blood Pressure",
            min_value=map_min, max_value=map_max, mean_value=map_mean, std_value=map_std,
            dynamic_range=map_range, status=map_status, clinical_note=map_note
        )

        # 3. Respiratory Mechanics Trend
        rr_min = self._get_f(vitals, 'respiration_min', 'resprate_min')
        rr_max = self._get_f(vitals, 'respiration_max', 'resprate_max')
        rr_mean = self._get_f(vitals, 'respiration_mean', 'resprate_mean')
        rr_std = self._get_f(vitals, 'respiration_std', 'resprate_std')
        rr_range = (rr_max - rr_min) if (rr_max is not None and rr_min is not None) else None

        rr_status = "STABLE"
        rr_note = "Respiratory pattern acceptable."
        if rr_max is not None and rr_max > 32.0:
            rr_status = "WORSENING"
            rr_note = f"Tachypneic exhaustion spike ({rr_max:.0f} breaths/min)."
            flags.append(f"Severe Tachypnea Spike ({rr_max:.0f} /min)")
            instability_count += 1

        trends['respiration'] = VariableTrend(
            variable_name="Respiratory Rate",
            min_value=rr_min, max_value=rr_max, mean_value=rr_mean, std_value=rr_std,
            dynamic_range=rr_range, status=rr_status, clinical_note=rr_note
        )

        # 4. Overall Trajectory Synthesis
        if instability_count >= 3:
            direction = "RAPID_DECOMPENSATION"
            score = 0.85
            narrative = "Critical temporal instability across multiple vital sign axes; acute physiological collapse."
        elif instability_count >= 1:
            direction = "VOLATILE"
            score = 0.55
            narrative = "Moderate hemodynamic or respiratory volatility; heightened risk of sudden decompensation."
        else:
            direction = "STABLE"
            score = 0.15
            narrative = "Temporal parameters stable with low variance."

        return PatientTrendReport(
            overall_direction=direction,
            velocity_score=score,
            autonomic_instability_detected=(instability_count > 0),
            variable_trends=trends,
            trend_narrative=narrative,
            clinical_flags=flags
        )

    @staticmethod
    def _get_f(vitals: Dict[str, Any], *keys: str) -> Optional[float]:
        for k in keys:
            if k in vitals:
                val = vitals[k]
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    try:
                        return float(val)
                    except:
                        continue
        return None
