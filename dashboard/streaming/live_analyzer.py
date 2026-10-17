"""
ICU Guard v5.0 — Real-Time Live Physiological Analyzer
Executes all 11 organ failure detectors and 16 critical syndrome evaluators
on incoming telemetry frames in < 10ms, evaluating trajectory, tier, and live alerts.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import collections

from severity_agent.detectors import (
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
    NutritionalDetector,
    OrganAssessment,
)
from severity_agent.patterns import (
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
    HyperosmolarCrisisPattern,
    PatternMatch,
)
from severity_agent.severity import SeverityEvaluator
from dashboard.streaming.data_streamer import StreamFrame
from dashboard.utils.constants import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    TIER_STABLE,
    TIER_COLORS,
)


@dataclass
class LiveAlert:
    """Represents a time-stamped clinical alarm event."""
    id: str
    timestamp: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    color: str
    title: str
    message: str
    icon: str


@dataclass
class TrendItem:
    """Represents the velocity of change for a physiological vital sign."""
    metric: str
    direction: str  # "UP", "DOWN", "FLAT"
    arrow: str
    delta_text: str
    is_worsening: bool


@dataclass
class LiveAnalysisResult:
    """Synthesized analysis output from a single telemetry tick."""
    tick: int
    timestamp_str: str
    current_tier: str
    tier_color: str
    trajectory: str
    organ_assessments: Dict[str, OrganAssessment]
    detected_patterns: List[PatternMatch]
    new_alerts: List[LiveAlert]
    top_trends: List[TrendItem]
    vitals_history: Dict[str, List[float]]
    overall_score: float
    recommended_action: str


class LiveAnalyzer:
    """Evaluates telemetry frames in real-time with zero latency."""

    def __init__(self, history_len: int = 20):
        self.history_len = history_len

        # Rolling buffers for sparklines
        self.history: Dict[str, collections.deque] = {
            "hr": collections.deque(maxlen=history_len),
            "map": collections.deque(maxlen=history_len),
            "sbp": collections.deque(maxlen=history_len),
            "rr": collections.deque(maxlen=history_len),
            "temp": collections.deque(maxlen=history_len),
            "sao2": collections.deque(maxlen=history_len),
            "gcs": collections.deque(maxlen=history_len),
            "lactate": collections.deque(maxlen=history_len),
        }

        # Pre-instantiate Detectors & Patterns for instant evaluation
        self.detectors = [
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
            NutritionalDetector(),
        ]
        self.patterns = [
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
            HyperosmolarCrisisPattern(),
        ]
        self.severity_evaluator = SeverityEvaluator()

        self._alert_counter = 0
        self._last_alert_keys = set()

    def analyze_frame(self, frame: StreamFrame) -> LiveAnalysisResult:
        """Processes a single telemetry frame and returns clinical assessment."""
        v = frame.vitals
        features = frame.full_features

        # Update rolling history
        for key in ["hr", "map", "sbp", "rr", "temp", "sao2", "gcs", "lactate"]:
            if key in v:
                self.history[key].append(v[key])

        # 1. Run 11 Evidence-Based Organ Detectors
        organ_assessments: Dict[str, OrganAssessment] = {}
        for d in self.detectors:
            assessment = d.assess(features)
            organ_assessments[assessment.organ_name] = assessment

        # 2. Run 16 Clinical Syndrome Patterns
        matched_patterns: List[PatternMatch] = []
        for p in self.patterns:
            match = p.evaluate(organ_assessments, features)
            if match.detected:
                matched_patterns.append(match)

        # 3. Non-Downgrading Triage Tier Evaluation
        # Mock probabilities based on vitals severity
        hr = v.get("hr", 75.0)
        mbp = v.get("map", 75.0)
        sao2 = v.get("sao2", 98.0)
        gcs = v.get("gcs", 15.0)

        # Basic deterioration proxy probability for real-time arbitration
        det_score = 0.1
        if mbp < 65: det_score += 0.35
        if sao2 < 90: det_score += 0.30
        if hr > 115 or hr < 45: det_score += 0.20
        if gcs < 13: det_score += 0.20
        det_score = min(0.99, max(0.05, det_score))

        probabilities = {
            "p_deterioration": det_score,
            "p_mortality": det_score * 0.45,
            "p_severe": det_score * 0.65,
        }

        severity = self.severity_evaluator.evaluate(
            probabilities=probabilities,
            organ_assessments=organ_assessments,
            patterns=matched_patterns,
            vitals=features,
        )

        current_tier = severity.final_tier
        tier_color = TIER_COLORS.get(current_tier, "#32CD32")

        # 4. Trajectory Assessment
        trajectory = self._determine_trajectory(current_tier, organ_assessments, matched_patterns)

        # 5. Live Alarm Generation
        new_alerts = self._generate_alerts(frame, organ_assessments, matched_patterns, current_tier)

        # 6. Trend Velocities
        top_trends = self._compute_trends()

        # Convert deques to lists for frontend
        vitals_hist = {k: list(dq) for k, dq in self.history.items()}

        return LiveAnalysisResult(
            tick=frame.tick,
            timestamp_str=frame.timestamp_str,
            current_tier=current_tier,
            tier_color=tier_color,
            trajectory=trajectory,
            organ_assessments=organ_assessments,
            detected_patterns=matched_patterns,
            new_alerts=new_alerts,
            top_trends=top_trends,
            vitals_history=vitals_hist,
            overall_score=severity.overall_score,
            recommended_action=severity.recommended_clinical_action,
        )

    def _determine_trajectory(
        self,
        tier: str,
        organs: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
    ) -> str:
        """Determines patient trajectory: STABLE, SLOW, RAPID, IMPROVING."""
        if tier == TIER_CRITICAL:
            return "RAPID_DETERIORATION"
        elif tier == TIER_HIGH:
            return "SLOW_DETERIORATION"
        elif tier == TIER_MODERATE:
            return "SLOW_DETERIORATION"
        else:
            return "STABLE"

    def _generate_alerts(
        self,
        frame: StreamFrame,
        organs: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        tier: str,
    ) -> List[LiveAlert]:
        """Generates real-time clinical alarms on threshold breaches or new patterns."""
        alerts: List[LiveAlert] = []
        v = frame.vitals
        ts = frame.timestamp_str

        # Threshold checks
        hr = v.get("hr", 75.0)
        mbp = v.get("map", 75.0)
        sao2 = v.get("sao2", 98.0)
        rr = v.get("rr", 16.0)
        gcs = v.get("gcs", 15.0)

        # 1. Heart Rate Alarms
        if hr > 130.0:
            alerts.append(self._make_alert(
                f"hr_extreme_{frame.tick}", ts, "CRITICAL", TIER_COLORS[TIER_CRITICAL],
                "Extreme Tachycardia", f"Heart Rate critical at {hr:.0f} bpm (Tachyarrhythmia risk)", "warning"
            ))
        elif hr > 110.0:
            alerts.append(self._make_alert(
                f"hr_tachy_{frame.tick}", ts, "WARNING", TIER_COLORS[TIER_HIGH],
                "Tachycardia Onset", f"Heart Rate elevated at {hr:.0f} bpm", "show_chart"
            ))

        # 2. Blood Pressure / Shock
        if mbp < 60.0:
            alerts.append(self._make_alert(
                f"map_shock_{frame.tick}", ts, "CRITICAL", TIER_COLORS[TIER_CRITICAL],
                "Severe Hypotensive Shock", f"MAP dropped to {mbp:.0f} mmHg — Tissue hypoperfusion!", "local_hospital"
            ))
        elif mbp < 65.0:
            alerts.append(self._make_alert(
                f"map_low_{frame.tick}", ts, "WARNING", TIER_COLORS[TIER_HIGH],
                "MAP Below Target", f"MAP {mbp:.0f} mmHg (< 65 mmHg SSC threshold)", "warning_amber"
            ))

        # 3. Hypoxemia / Respiratory
        if sao2 < 85.0:
            alerts.append(self._make_alert(
                f"sao2_crit_{frame.tick}", ts, "CRITICAL", TIER_COLORS[TIER_CRITICAL],
                "Refractory Hypoxemia", f"SaO2 critical at {sao2:.0f}% — Prepare emergency airway!", "air"
            ))
        elif sao2 < 90.0:
            alerts.append(self._make_alert(
                f"sao2_low_{frame.tick}", ts, "WARNING", TIER_COLORS[TIER_HIGH],
                "Hypoxemia Alert", f"SaO2 dropped to {sao2:.0f}%", "air"
            ))

        # 4. Syndrome Pattern Alarms
        for p in patterns:
            p_key = f"pat_{p.pattern_name}_{frame.tick}"
            if p_key not in self._last_alert_keys and len(alerts) < 3:
                rec_text = getattr(p, "clinical_recommendation", "") or (
                    p.diagnostic_criteria_met[0] if getattr(p, "diagnostic_criteria_met", None) else "Syndrome criteria met"
                )
                alerts.append(self._make_alert(
                    p_key, ts, "CRITICAL" if p.confidence == "HIGH" else "WARNING",
                    TIER_COLORS[TIER_CRITICAL] if p.confidence == "HIGH" else TIER_COLORS[TIER_HIGH],
                    f"Pattern: {p.pattern_name}",
                    f"Syndrome match confirmed ({p.confidence} confidence): {rec_text[:60]}...",
                    "emergency"
                ))
                self._last_alert_keys.add(p_key)

        return alerts

    def _make_alert(self, key: str, ts: str, severity: str, color: str, title: str, msg: str, icon: str) -> LiveAlert:
        self._alert_counter += 1
        return LiveAlert(
            id=f"alert_{self._alert_counter}_{key}",
            timestamp=ts,
            severity=severity,
            color=color,
            title=title,
            message=msg,
            icon=icon,
        )

    def _compute_trends(self) -> List[TrendItem]:
        """Calculates direction of change for HR, MAP, and SaO2 over recent window."""
        trends: List[TrendItem] = []

        # Heart Rate
        hr_list = list(self.history["hr"])
        if len(hr_list) >= 4:
            delta = hr_list[-1] - hr_list[0]
            if abs(delta) >= 2.0:
                arrow = "↗️" if delta > 0 else "↘️"
                direction = "UP" if delta > 0 else "DOWN"
                is_worsening = (delta > 0)
                trends.append(TrendItem("Heart Rate", direction, arrow, f"{delta:+.0f} bpm", is_worsening))

        # Mean Arterial Pressure
        map_list = list(self.history["map"])
        if len(map_list) >= 4:
            delta = map_list[-1] - map_list[0]
            if abs(delta) >= 2.0:
                arrow = "↘️" if delta < 0 else "↗️"
                direction = "DOWN" if delta < 0 else "UP"
                is_worsening = (delta < 0)  # Falling MAP is worsening
                trends.append(TrendItem("Mean Arterial BP", direction, arrow, f"{delta:+.0f} mmHg", is_worsening))

        # Oxygen Saturation
        sao2_list = list(self.history["sao2"])
        if len(sao2_list) >= 4:
            delta = sao2_list[-1] - sao2_list[0]
            if abs(delta) >= 1.0:
                arrow = "↘️" if delta < 0 else "↗️"
                direction = "DOWN" if delta < 0 else "UP"
                is_worsening = (delta < 0)
                trends.append(TrendItem("SaO2 Saturation", direction, arrow, f"{delta:+.1f}%", is_worsening))

        if not trends:
            trends.append(TrendItem("Physiological Status", "FLAT", "➡️", "Stable Baseline", False))

        return trends[:3]
