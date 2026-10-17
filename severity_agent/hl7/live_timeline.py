"""
live_timeline.py — Continuous Multi-Event Bedside Clinical Timeline
===================================================================
Coordinates and logs live chronological events (telemetry arrivals,
periodic continuous predictions, tier change alerts, pattern discoveries).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TimelineEvent:
    """A discrete chronological bedside event."""
    id: int
    event_type: str        # 'PREDICTION', 'TIER_CHANGE', 'PATTERN', 'TELEMETRY', 'ALERT'
    sim_time_minutes: float
    sim_time_str: str
    timestamp: str
    title: str
    description: str
    severity: str          # 'INFO', 'SUCCESS', 'WARNING', 'CRITICAL'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveTimeline:
    """
    Thread-safe longitudinal event store for a patient's bedside timeline.
    """

    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self._lock = threading.Lock()
        self._counter = 0
        self._events: Dict[str, List[TimelineEvent]] = {}

    def add_event(
        self,
        patient_id: str,
        event_type: str,
        sim_time_minutes: float,
        sim_time_str: str,
        title: str,
        description: str,
        severity: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> TimelineEvent:
        """Appends a new clinical event to the timeline."""
        with self._lock:
            self._counter += 1
            now_iso = timestamp or datetime.now().isoformat()
            evt = TimelineEvent(
                id=self._counter,
                event_type=event_type,
                sim_time_minutes=sim_time_minutes,
                sim_time_str=sim_time_str,
                timestamp=now_iso,
                title=title,
                description=description,
                severity=severity,
                metadata=metadata or {},
            )
            if patient_id not in self._events:
                self._events[patient_id] = []
            self._events[patient_id].append(evt)

            if len(self._events[patient_id]) > self.max_events:
                self._events[patient_id].pop(0)

            return evt

    def get_events(
        self,
        patient_id: str,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> List[TimelineEvent]:
        """Returns chronological list of events for a patient."""
        with self._lock:
            evts = self._events.get(patient_id, [])
            if event_type:
                evts = [e for e in evts if e.event_type == event_type]
            if limit:
                return evts[-limit:]
            return list(evts)

    def clear(self, patient_id: Optional[str] = None) -> None:
        """Clears timeline events."""
        with self._lock:
            if patient_id:
                self._events.pop(patient_id, None)
            else:
                self._events.clear()
