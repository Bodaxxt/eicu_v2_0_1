"""
history.py — Longitudinal Prediction History & Delta Tracker
============================================================
Stores periodic continuous predictions, tracks risk probability deltas,
records detected clinical patterns, and provides persistence via SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PredictionRecord:
    """Represents a single point-in-time clinical prediction snapshot."""
    id: Optional[int] = None
    patient_id: str = ""
    timestamp: str = ""
    sim_time_minutes: float = 0.0
    sim_time_str: str = "00:00"
    mortality_risk: float = 0.0
    deterioration_risk: float = 0.0
    severe_risk: float = 0.0
    predicted_tier: str = "STABLE"
    effective_tier: str = "STABLE"
    trajectory: str = "STABLE"
    delta_mortality: float = 0.0
    delta_deterioration: float = 0.0
    delta_severe: float = 0.0
    active_patterns: List[Dict[str, Any]] = field(default_factory=list)
    features_snapshot: Dict[str, Any] = field(default_factory=dict)
    raw_assessment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PredictionHistory:
    """
    Manages time-series prediction history with SQLite backing and in-memory cache.
    Thread-safe implementation suitable for continuous background execution.
    """

    DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "dashboard" / "cache" / "icu_prediction_history.db"

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            self.db_path = self.DEFAULT_DB_PATH
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)

        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._cache: Dict[str, List[PredictionRecord]] = {}
        self._init_sqlite()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if not hasattr(self, "_mem_conn") or self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            return self._mem_conn
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _init_sqlite(self) -> None:
        """Initializes the database schema."""
        with self._lock:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS icu_prediction_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    sim_time_minutes REAL NOT NULL,
                    sim_time_str TEXT NOT NULL,
                    mortality_risk REAL NOT NULL,
                    deterioration_risk REAL NOT NULL,
                    severe_risk REAL NOT NULL,
                    predicted_tier TEXT NOT NULL,
                    effective_tier TEXT NOT NULL,
                    trajectory TEXT NOT NULL,
                    delta_mortality REAL NOT NULL,
                    delta_deterioration REAL NOT NULL,
                    delta_severe REAL NOT NULL,
                    active_patterns TEXT,
                    features_snapshot TEXT,
                    raw_assessment TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pred_patient ON icu_prediction_history(patient_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pred_sim_time ON icu_prediction_history(patient_id, sim_time_minutes)")
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    @staticmethod
    def format_sim_time(sim_minutes: float) -> str:
        """Converts minutes to HH:MM format."""
        total_mins = int(round(sim_minutes))
        hours = total_mins // 60
        mins = total_mins % 60
        return f"{hours:02d}:{mins:02d}"

    def add_prediction(
        self,
        patient_id: str,
        assessment_dict: Dict[str, Any],
        sim_time_minutes: float,
        trajectory: str = "STABLE",
        effective_tier: Optional[str] = None,
        features_snapshot: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> PredictionRecord:
        """
        Records a new prediction, calculating deltas relative to the previous point.
        """
        with self._lock:
            now_iso = timestamp or datetime.now().isoformat()
            sim_str = self.format_sim_time(sim_minutes=sim_time_minutes)

            probs = assessment_dict.get("probabilities", {})
            mort_risk = float(probs.get("mortality_risk", probs.get("p_mortality", 0.0)))
            det_risk = float(probs.get("deterioration_risk", probs.get("p_deterioration", 0.0)))
            sev_risk = float(probs.get("severe_risk", probs.get("p_severe", 0.0)))
            raw_tier = str(assessment_dict.get("severity_tier", "STABLE"))
            eff_tier = effective_tier or raw_tier

            # Extract active patterns
            patterns_data = assessment_dict.get("patterns", [])
            active_patterns = [p for p in patterns_data if p.get("detected")] if isinstance(patterns_data, list) else []

            # Retrieve previous record for deltas
            prev = self._get_latest_unlocked(patient_id)
            if prev:
                delta_mort = mort_risk - prev.mortality_risk
                delta_det = det_risk - prev.deterioration_risk
                delta_sev = sev_risk - prev.severe_risk
            else:
                delta_mort = 0.0
                delta_det = 0.0
                delta_sev = 0.0

            feats = features_snapshot or {}

            # Insert into SQLite
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO icu_prediction_history (
                    patient_id, timestamp, sim_time_minutes, sim_time_str,
                    mortality_risk, deterioration_risk, severe_risk,
                    predicted_tier, effective_tier, trajectory,
                    delta_mortality, delta_deterioration, delta_severe,
                    active_patterns, features_snapshot, raw_assessment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient_id, now_iso, sim_time_minutes, sim_str,
                mort_risk, det_risk, sev_risk,
                raw_tier, eff_tier, trajectory,
                delta_mort, delta_det, delta_sev,
                json.dumps(active_patterns), json.dumps(feats), json.dumps(assessment_dict)
            ))
            row_id = cur.lastrowid
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

            record = PredictionRecord(
                id=row_id,
                patient_id=patient_id,
                timestamp=now_iso,
                sim_time_minutes=sim_time_minutes,
                sim_time_str=sim_str,
                mortality_risk=mort_risk,
                deterioration_risk=det_risk,
                severe_risk=sev_risk,
                predicted_tier=raw_tier,
                effective_tier=eff_tier,
                trajectory=trajectory,
                delta_mortality=delta_mort,
                delta_deterioration=delta_det,
                delta_severe=delta_sev,
                active_patterns=active_patterns,
                features_snapshot=feats,
                raw_assessment=assessment_dict,
            )

            # Update cache
            if patient_id not in self._cache:
                self._cache[patient_id] = []
            self._cache[patient_id].append(record)

            return record

    def _get_latest_unlocked(self, patient_id: str) -> Optional[PredictionRecord]:
        """Internal helper to get latest record without acquiring lock twice."""
        if patient_id in self._cache and self._cache[patient_id]:
            return self._cache[patient_id][-1]

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, patient_id, timestamp, sim_time_minutes, sim_time_str,
                   mortality_risk, deterioration_risk, severe_risk,
                   predicted_tier, effective_tier, trajectory,
                   delta_mortality, delta_deterioration, delta_severe,
                   active_patterns, features_snapshot, raw_assessment
            FROM icu_prediction_history
            WHERE patient_id = ?
            ORDER BY sim_time_minutes DESC, id DESC
            LIMIT 1
        """, (patient_id,))
        row = cur.fetchone()
        if self.db_path != ":memory:":
            conn.close()

        if row:
            rec = self._row_to_record(row)
            return rec
        return None

    def get_latest(self, patient_id: str) -> Optional[PredictionRecord]:
        """Returns the most recent prediction record for a patient."""
        with self._lock:
            return self._get_latest_unlocked(patient_id)

    def get_history(self, patient_id: str, limit: Optional[int] = None) -> List[PredictionRecord]:
        """Returns chronological list of predictions for a patient."""
        with self._lock:
            if patient_id in self._cache and self._cache[patient_id]:
                records = self._cache[patient_id]
                if limit:
                    return records[-limit:]
                return list(records)

            conn = self._get_connection()
            cur = conn.cursor()
            query = """
                SELECT id, patient_id, timestamp, sim_time_minutes, sim_time_str,
                       mortality_risk, deterioration_risk, severe_risk,
                       predicted_tier, effective_tier, trajectory,
                       delta_mortality, delta_deterioration, delta_severe,
                       active_patterns, features_snapshot, raw_assessment
                FROM icu_prediction_history
                WHERE patient_id = ?
                ORDER BY sim_time_minutes ASC, id ASC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            cur.execute(query, (patient_id,))
            rows = cur.fetchall()
            if self.db_path != ":memory:":
                conn.close()

            records = [self._row_to_record(r) for r in rows]
            self._cache[patient_id] = list(records)
            return records

    def get_deltas(self, patient_id: str) -> Dict[str, float]:
        """Calculates latest deltas and cumulative deltas from start."""
        history = self.get_history(patient_id)
        if not history:
            return {
                "step_mortality": 0.0, "step_deterioration": 0.0, "step_severe": 0.0,
                "total_mortality": 0.0, "total_deterioration": 0.0, "total_severe": 0.0,
            }
        latest = history[-1]
        first = history[0]
        return {
            "step_mortality": latest.delta_mortality,
            "step_deterioration": latest.delta_deterioration,
            "step_severe": latest.delta_severe,
            "total_mortality": latest.mortality_risk - first.mortality_risk,
            "total_deterioration": latest.deterioration_risk - first.deterioration_risk,
            "total_severe": latest.severe_risk - first.severe_risk,
        }

    def clear_history(self, patient_id: Optional[str] = None) -> None:
        """Clears records for a single patient or all patients."""
        with self._lock:
            conn = self._get_connection()
            cur = conn.cursor()
            if patient_id:
                cur.execute("DELETE FROM icu_prediction_history WHERE patient_id = ?", (patient_id,))
                self._cache.pop(patient_id, None)
            else:
                cur.execute("DELETE FROM icu_prediction_history")
                self._cache.clear()
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()

    def _row_to_record(self, row: tuple) -> PredictionRecord:
        (
            rid, pid, tstamp, sim_min, sim_str,
            mort, det, sev,
            pred_tier, eff_tier, traj,
            d_mort, d_det, d_sev,
            pats, feats, raw_assess
        ) = row
        return PredictionRecord(
            id=rid,
            patient_id=pid,
            timestamp=tstamp,
            sim_time_minutes=float(sim_min),
            sim_time_str=sim_str,
            mortality_risk=float(mort),
            deterioration_risk=float(det),
            severe_risk=float(sev),
            predicted_tier=pred_tier,
            effective_tier=eff_tier,
            trajectory=traj,
            delta_mortality=float(d_mort),
            delta_deterioration=float(d_det),
            delta_severe=float(d_sev),
            active_patterns=json.loads(pats) if pats else [],
            features_snapshot=json.loads(feats) if feats else {},
            raw_assessment=json.loads(raw_assess) if raw_assess else {},
        )
