"""
trajectory.py — Clinical Trajectory & Deterioration Velocity Analyzer
=====================================================================
Analyzes historical longitudinal risk probability windows to compute:
1. Trajectory classification: STABLE, SLOW_DETERIORATION, RAPID_DETERIORATION, IMPROVING
2. Rate of change (velocity) per hour for Mortality, Deterioration, and Severe Acuity
3. Estimated time-to-critical countdown (minutes until reaching 85% deterioration risk)
4. Model trajectory confidence estimation
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from .history import PredictionRecord


@dataclass
class TrajectoryResult:
    """Contains velocity metrics and trajectory classification."""
    trajectory_type: str                  # STABLE, SLOW_DETERIORATION, RAPID_DETERIORATION, IMPROVING
    rate_of_change_per_hour: float        # Hourly slope of deterioration risk (e.g. +0.15 = +15%/hr)
    mortality_rate_per_hour: float        # Hourly slope of mortality risk
    severe_rate_per_hour: float           # Hourly slope of severe risk
    time_to_critical_minutes: Optional[float]  # Projected minutes to cross 85% deterioration (or None)
    confidence: float                     # 0.0 to 1.0
    summary: str                          # Clinical summary text
    acceleration: float = 0.0             # Second derivative (change of slope)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrajectoryAnalyzer:
    """
    Computes trajectory classifications and rate-of-change metrics
    over a rolling window of recent PredictionRecords.
    """

    CRITICAL_THRESHOLD: float = 0.85
    RAPID_DETERIORATION_SLOPE: float = 0.08    # +8% / hour or more
    SLOW_DETERIORATION_SLOPE: float = 0.02     # +2% to +8% / hour
    IMPROVING_SLOPE: float = -0.02             # -2% / hour or less

    @classmethod
    def analyze(
        cls,
        history: List[PredictionRecord],
        window_minutes: float = 60.0,
    ) -> TrajectoryResult:
        """
        Analyzes the trajectory of the given history records.
        Uses records within the last `window_minutes` (or at least the last 2 records).
        """
        if not history or len(history) < 2:
            return TrajectoryResult(
                trajectory_type="STABLE",
                rate_of_change_per_hour=0.0,
                mortality_rate_per_hour=0.0,
                severe_rate_per_hour=0.0,
                time_to_critical_minutes=None,
                confidence=0.50,
                summary="Insufficient longitudinal history to compute trajectory (< 2 predictions).",
            )

        # Filter window
        latest_sim_min = history[-1].sim_time_minutes
        min_cutoff = latest_sim_min - window_minutes
        window = [r for r in history if r.sim_time_minutes >= min_cutoff]
        if len(window) < 2:
            window = history[-min(len(history), 6):]

        # Extract time in hours and probabilities
        t_hours = [(r.sim_time_minutes - window[0].sim_time_minutes) / 60.0 for r in window]
        det_risks = [r.deterioration_risk for r in window]
        mort_risks = [r.mortality_risk for r in window]
        sev_risks = [r.severe_risk for r in window]

        # Linear regression for slopes
        det_slope, det_r2 = cls._linear_regression(t_hours, det_risks)
        mort_slope, _ = cls._linear_regression(t_hours, mort_risks)
        sev_slope, _ = cls._linear_regression(t_hours, sev_risks)

        # Acceleration (comparing first half vs second half slope if >= 4 points)
        accel = 0.0
        if len(window) >= 4:
            mid = len(window) // 2
            slope1, _ = cls._linear_regression(t_hours[:mid], det_risks[:mid])
            slope2, _ = cls._linear_regression(t_hours[mid:], det_risks[mid:])
            accel = slope2 - slope1

        # Determine trajectory category
        if det_slope >= cls.RAPID_DETERIORATION_SLOPE or (det_slope >= cls.SLOW_DETERIORATION_SLOPE and accel > 0.05):
            traj_type = "RAPID_DETERIORATION"
        elif det_slope >= cls.SLOW_DETERIORATION_SLOPE:
            traj_type = "SLOW_DETERIORATION"
        elif det_slope <= cls.IMPROVING_SLOPE:
            traj_type = "IMPROVING"
        else:
            traj_type = "STABLE"

        # Time to critical estimation
        current_det = det_risks[-1]
        time_to_crit: Optional[float] = None
        if det_slope > 0.001 and current_det < cls.CRITICAL_THRESHOLD:
            hours_left = (cls.CRITICAL_THRESHOLD - current_det) / det_slope
            mins_left = hours_left * 60.0
            if 0 < mins_left <= 720:  # within 12 hours
                time_to_crit = round(mins_left, 1)

        # Confidence computation based on R^2 and sample size
        n_pts = len(window)
        pts_factor = min(1.0, n_pts / 6.0)
        confidence = round(max(0.40, min(0.99, (det_r2 * 0.6) + (pts_factor * 0.4))), 2)

        # Human-readable summary
        pct_slope = det_slope * 100.0
        if traj_type == "RAPID_DETERIORATION":
            summary = (
                f"Rapid Deterioration (+{pct_slope:.1f}%/hr). "
                + (f"Projected Critical in ~{int(time_to_crit)} mins." if time_to_crit else "High vigilance required.")
            )
        elif traj_type == "SLOW_DETERIORATION":
            summary = (
                f"Gradual Deterioration (+{pct_slope:.1f}%/hr). "
                + (f"Estimated Critical in ~{int(time_to_crit)} mins." if time_to_crit else "Close monitoring indicated.")
            )
        elif traj_type == "IMPROVING":
            summary = f"Favorable Trajectory ({pct_slope:.1f}%/hr). Patient stabilizing under current therapy."
        else:
            summary = "Stable physiological trajectory. Risk metrics remain bounded within nominal ranges."

        return TrajectoryResult(
            trajectory_type=traj_type,
            rate_of_change_per_hour=round(det_slope, 4),
            mortality_rate_per_hour=round(mort_slope, 4),
            severe_rate_per_hour=round(sev_slope, 4),
            time_to_critical_minutes=time_to_crit,
            confidence=confidence,
            summary=summary,
            acceleration=round(accel, 4),
        )

    @staticmethod
    def _linear_regression(x: List[float], y: List[float]) -> tuple[float, float]:
        """Calculates slope and R^2 coefficient of determination."""
        n = len(x)
        if n < 2:
            return 0.0, 0.5
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        den_x = sum((x[i] - mean_x) ** 2 for i in range(n))
        den_y = sum((y[i] - mean_y) ** 2 for i in range(n))

        if den_x == 0:
            return 0.0, 0.5

        slope = num / den_x
        if den_y == 0:
            r2 = 1.0 if abs(slope) < 1e-6 else 0.0
        else:
            r = num / (math.sqrt(den_x) * math.sqrt(den_y)) if den_x > 0 and den_y > 0 else 0.0
            r2 = r ** 2

        return slope, r2
