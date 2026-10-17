"""
buffer.py — In-Memory Clinical Time-Series Data Buffer
======================================================
Stores and manages longitudinal bedside observations per patient,
enforcing a rolling 6-hour clinical observation window for ICU Guard features.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .parser import ParsedObservation, ParsedHL7Message

logger = logging.getLogger("icu_guard.hl7.buffer")


@dataclass
class TimestampedValue:
    """A single numeric observation with timestamp and metadata."""
    timestamp: datetime
    value: float
    flag: str
    unit: str


class PatientDataBuffer:
    """
    Manages longitudinal telemetry and laboratory observations for a single patient.
    """

    def __init__(self, patient_id: str, window_hours: float = 6.0):
        self.patient_id = patient_id
        self.window_hours = window_hours
        # Mapping: LOINC code -> list of TimestampedValue
        self._history: Dict[str, List[TimestampedValue]] = defaultdict(list)
        # Mapping: Canonical feature name -> LOINC code
        self._canonical_to_loinc: Dict[str, str] = {}
        # Patient static demographics / comorbidities
        self.demographics: Dict[str, Any] = {
            "age": 65.0,
            "gender": 1,         # 1=Male, 0=Female
            "admissionweight": 75.0,
            "admissionheight": 172.0,
            "bmi": 25.35,
            "has_diabetes": 0,
            "has_ckd": 0,
            "has_chf": 0,
            "has_copd": 0,
            "has_hypertension": 0,
            "apachescore": 45.0,
            "acutephysiologyscore": 38.0,
            "predictedicumortality": 0.12,
            "predictediculos": 3.5,
            "gcs_min": 15.0,
            "gcs_mean": 15.0,
            "total_urine_6h": 600.0,
        }
        self.last_updated: datetime = datetime.now()

    def add_message(self, msg: ParsedHL7Message) -> None:
        """Ingest all observations from a parsed HL7 message."""
        for obs in msg.observations:
            self.add_observation(obs)
        self.last_updated = msg.timestamp

    def add_observation(self, obs: ParsedObservation) -> None:
        """Add a single observation into the patient buffer."""
        entry = TimestampedValue(
            timestamp=obs.timestamp,
            value=obs.value,
            flag=obs.flag,
            unit=obs.unit,
        )
        self._history[obs.loinc].append(entry)
        if obs.name:
            self._canonical_to_loinc[obs.name.upper()] = obs.loinc
        self.last_updated = max(self.last_updated, obs.timestamp)

    def prune_outside_window(self, reference_time: Optional[datetime] = None) -> int:
        """
        Discard readings older than `window_hours` before reference_time.
        Returns the count of purged readings.
        """
        ref_time = reference_time or self.last_updated
        cutoff = ref_time - timedelta(hours=self.window_hours)
        purged = 0

        for loinc, series in list(self._history.items()):
            valid_entries = [e for e in series if e.timestamp >= cutoff]
            purged += len(series) - len(valid_entries)
            if valid_entries:
                self._history[loinc] = valid_entries
            else:
                del self._history[loinc]

        return purged

    def get_stats(self, loinc_code: str) -> Tuple[float, float, float, float, int]:
        """
        Calculate (mean, min, max, std, count) for a given LOINC code within the window.
        Returns (nan, nan, nan, nan, 0) if no data exists.
        """
        series = self._history.get(loinc_code, [])
        if not series:
            return float("nan"), float("nan"), float("nan"), float("nan"), 0

        values = [e.value for e in series]
        n = len(values)
        mean_val = sum(values) / n
        min_val = min(values)
        max_val = max(values)

        if n > 1:
            variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
            std_val = math.sqrt(variance)
        else:
            std_val = 0.0

        return mean_val, min_val, max_val, std_val, n

    def get_latest(self, loinc_code: str) -> Optional[float]:
        """Return the most recently recorded measurement value."""
        series = self._history.get(loinc_code, [])
        if not series:
            return None
        return series[-1].value

    def get_all_loinc_codes(self) -> List[str]:
        """Return list of all LOINC codes recorded in the buffer."""
        return list(self._history.keys())

    def total_observation_count(self) -> int:
        """Total number of stored observation points across all parameters."""
        return sum(len(series) for series in self._history.values())
