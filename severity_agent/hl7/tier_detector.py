"""
tier_detector.py — Monotonic Non-Downgrading Tier Transition & Alert Detector
=============================================================================
Enforces clinical safety non-downgrading semantics: once a patient escalates
to a higher acuity tier (e.g. MODERATE -> HIGH -> CRITICAL), the clinical tier
does not silently downgrade, and an escalation event is emitted for bedside alert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("icu_guard.hl7.tier_detector")


@dataclass
class TierChangeEvent:
    """Represents an acute clinical acuity tier escalation event."""
    patient_id: str
    previous_tier: str
    new_tier: str
    sim_time_minutes: float
    sim_time_str: str
    timestamp: str
    trigger_reason: str
    mortality_risk: float = 0.0
    deterioration_risk: float = 0.0
    severe_risk: float = 0.0
    active_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def summary(self) -> str:
        return f"[{self.sim_time_str}] Tier Escalation: {self.previous_tier} ➔ {self.new_tier} ({self.trigger_reason})"


class TierChangeDetector:
    """
    Monitors periodic predictions, enforces monotonic non-downgrading,
    and detects transitions between clinical tiers.
    """

    TIER_ORDER: Dict[str, int] = {
        "STABLE": 0,
        "MODERATE": 1,
        "HIGH": 2,
        "CRITICAL": 3,
    }

    ORDER_TO_TIER: Dict[int, str] = {
        0: "STABLE",
        1: "MODERATE",
        2: "HIGH",
        3: "CRITICAL",
    }

    def __init__(self, non_downgrading: bool = True):
        self.non_downgrading = non_downgrading
        # Patient ID -> highest tier achieved so far
        self._highest_tier: Dict[str, str] = {}
        # Patient ID -> list of tier escalation events
        self._events: Dict[str, List[TierChangeEvent]] = {}
        # Listeners for tier change events
        self._listeners: List[Callable[[TierChangeEvent], None]] = []

    @classmethod
    def normalize_tier(cls, raw: str) -> str:
        """Normalizes tier strings into STABLE, MODERATE, HIGH, CRITICAL."""
        t = str(raw).strip().upper()
        if "CRIT" in t or "TIER 1" in t:
            return "CRITICAL"
        if "HIGH" in t or "TIER 2" in t:
            return "HIGH"
        if "MOD" in t or "TIER 3" in t:
            return "MODERATE"
        return "STABLE"

    def register_listener(self, callback: Callable[[TierChangeEvent], None]) -> None:
        """Registers a callback to be notified when a tier change occurs."""
        self._listeners.append(callback)

    def evaluate(
        self,
        patient_id: str,
        raw_tier: str,
        probabilities: Dict[str, float],
        sim_time_minutes: float,
        sim_time_str: str,
        active_patterns: Optional[List[Any]] = None,
        reason: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Tuple[str, Optional[TierChangeEvent]]:
        """
        Evaluates a patient's new prediction.
        Returns:
            (effective_tier, tier_change_event_if_escalated)
        """
        norm_raw = self.normalize_tier(raw_tier)
        raw_order = self.TIER_ORDER.get(norm_raw, 0)

        prev_tier = self._highest_tier.get(patient_id, "STABLE")
        prev_order = self.TIER_ORDER.get(prev_tier, 0)

        now_iso = timestamp or datetime.now().isoformat()
        pattern_names = []
        if active_patterns:
            for p in active_patterns:
                if isinstance(p, dict):
                    pattern_names.append(p.get("name", "Unknown Pattern"))
                else:
                    pattern_names.append(str(p))

        det_risk = float(probabilities.get("deterioration_risk", 0.0))
        mort_risk = float(probabilities.get("mortality_risk", 0.0))
        sev_risk = float(probabilities.get("severe_risk", 0.0))

        # Check for escalation
        if raw_order > prev_order:
            new_effective = norm_raw
            self._highest_tier[patient_id] = new_effective

            trigger = reason
            if not trigger:
                if pattern_names:
                    trigger = f"Pattern detected: {', '.join(pattern_names[:2])}"
                elif det_risk >= 0.80:
                    trigger = f"Severe deterioration risk ({det_risk*100:.1f}%)"
                else:
                    trigger = f"Acuity threshold crossed ({norm_raw})"

            event = TierChangeEvent(
                patient_id=patient_id,
                previous_tier=prev_tier,
                new_tier=new_effective,
                sim_time_minutes=sim_time_minutes,
                sim_time_str=sim_time_str,
                timestamp=now_iso,
                trigger_reason=trigger,
                mortality_risk=mort_risk,
                deterioration_risk=det_risk,
                severe_risk=sev_risk,
                active_patterns=pattern_names,
            )

            if patient_id not in self._events:
                self._events[patient_id] = []
            self._events[patient_id].append(event)

            # Fire listeners
            for cb in self._listeners:
                try:
                    cb(event)
                except Exception as e:
                    logger.error(f"[TierChangeDetector] Listener error: {e}")

            logger.warning(
                f"[TierChangeDetector] Patient {patient_id} ESCALATED: "
                f"{prev_tier} ➔ {new_effective} at {sim_time_str} ({trigger})"
            )
            return new_effective, event

        # Non-downgrading enforcement
        if self.non_downgrading:
            effective = prev_tier
        else:
            effective = norm_raw
            self._highest_tier[patient_id] = effective

        return effective, None

    def get_tier_changes(self, patient_id: str) -> List[TierChangeEvent]:
        """Returns all recorded tier change events for a patient."""
        return list(self._events.get(patient_id, []))

    def get_effective_tier(self, patient_id: str) -> str:
        """Returns the current highest effective tier for a patient."""
        return self._highest_tier.get(patient_id, "STABLE")

    def reset(self, patient_id: Optional[str] = None) -> None:
        """Resets tracking state."""
        if patient_id:
            self._highest_tier.pop(patient_id, None)
            self._events.pop(patient_id, None)
        else:
            self._highest_tier.clear()
            self._events.clear()
