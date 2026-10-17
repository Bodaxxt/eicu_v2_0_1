"""
scheduler.py — Continuous Prediction Scheduler
===============================================
Executes periodic longitudinal clinical risk evaluations every 5 simulated minutes,
orchestrates SeverityAgent reasoning, tracks trajectory velocities, detects acute
tier escalations, and persists time-series history for real-time ICU surveillance.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from .history import PredictionHistory, PredictionRecord
from .tier_detector import TierChangeDetector, TierChangeEvent
from .trajectory import TrajectoryAnalyzer, TrajectoryResult
from .live_timeline import LiveTimeline
from severity_agent.agent import SeverityAgent

logger = logging.getLogger("icu_guard.hl7.scheduler")


class PredictionScheduler:
    """
    Continuous Asynchronous Clinical Assessment Scheduler.
    Executes assessments at fixed intervals (default: 5 simulated minutes).
    """

    DEFAULT_BUNDLE_PATH = "model_artifacts/icu_guard_v4_2_agent_bundle.pkl"

    def __init__(
        self,
        agent: Optional[SeverityAgent] = None,
        bundle_path: Optional[str] = None,
        history: Optional[PredictionHistory] = None,
        tier_detector: Optional[TierChangeDetector] = None,
        timeline: Optional[LiveTimeline] = None,
        interval_sim_minutes: float = 5.0,
        speed_multiplier: float = 1.0,
    ):
        self.interval_sim_minutes = interval_sim_minutes
        self.speed_multiplier = speed_multiplier

        self.history = history or PredictionHistory()
        self.tier_detector = tier_detector or TierChangeDetector(non_downgrading=True)
        self.timeline = timeline or LiveTimeline()

        # Wire tier change event listener to timeline
        self.tier_detector.register_listener(self._on_tier_escalated)

        # Initialize or resolve SeverityAgent
        if agent is not None:
            self.agent: Optional[SeverityAgent] = agent
        else:
            resolved_bundle = bundle_path or self.DEFAULT_BUNDLE_PATH
            if not os.path.exists(resolved_bundle):
                alt_path = os.path.join(os.path.dirname(__file__), "..", "..", resolved_bundle)
                if os.path.exists(alt_path):
                    resolved_bundle = alt_path

            if os.path.exists(resolved_bundle):
                try:
                    logger.info(f"[PredictionScheduler] Loading SeverityAgent from: {resolved_bundle}")
                    self.agent = SeverityAgent(bundle_path=resolved_bundle)
                except Exception as e:
                    logger.warning(f"[PredictionScheduler] Failed to load agent bundle: {e}. Using fallback evaluator.")
                    self.agent = None
            else:
                self.agent = None

        # Execution State
        self.is_running = False
        self.is_paused = False
        self.current_sim_time = 0.0      # In minutes
        self.active_patient_id: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        # Callbacks
        self.on_prediction: Optional[Callable[[PredictionRecord], None]] = None
        self.on_tier_change: Optional[Callable[[TierChangeEvent], None]] = None
        self.on_tick: Optional[Callable[[float, str], None]] = None

    def _on_tier_escalated(self, event: TierChangeEvent) -> None:
        """Internal callback invoked by TierChangeDetector."""
        self.timeline.add_event(
            patient_id=event.patient_id,
            event_type="TIER_CHANGE",
            sim_time_minutes=event.sim_time_minutes,
            sim_time_str=event.sim_time_str,
            title=f"Tier Escalation: {event.previous_tier} ➔ {event.new_tier}",
            description=event.trigger_reason,
            severity="CRITICAL" if event.new_tier == "CRITICAL" else "WARNING",
            metadata=event.to_dict(),
        )
        if self.on_tier_change:
            try:
                self.on_tier_change(event)
            except Exception as e:
                logger.error(f"[PredictionScheduler] on_tier_change error: {e}")

    def set_speed(self, multiplier: float) -> None:
        """Updates simulation speed multiplier (e.g. 1.0, 5.0, 10.0, 60.0)."""
        self.speed_multiplier = max(0.1, float(multiplier))
        logger.info(f"[PredictionScheduler] Speed set to {self.speed_multiplier}x")

    async def start(
        self,
        patient_id: str,
        total_hours: float = 10.0,
        start_sim_time: float = 0.0,
        speed_multiplier: Optional[float] = None,
        feature_provider: Optional[Callable[[float], Dict[str, Any]]] = None,
    ) -> None:
        """Starts continuous periodic prediction loop."""
        if speed_multiplier is not None:
            self.set_speed(speed_multiplier)

        if self.is_running:
            await self.stop()

        self.active_patient_id = patient_id
        self.current_sim_time = start_sim_time
        self.is_running = True
        self.is_paused = False
        self._stop_event.clear()

        self._task = asyncio.create_task(
            self._run_loop(
                patient_id=patient_id,
                total_hours=total_hours,
                feature_provider=feature_provider,
            )
        )

    def pause(self) -> None:
        """Pauses the continuous scheduler."""
        self.is_paused = True
        logger.info("[PredictionScheduler] Paused.")

    def resume(self) -> None:
        """Resumes the continuous scheduler."""
        self.is_paused = False
        logger.info("[PredictionScheduler] Resumed.")

    async def stop(self) -> None:
        """Stops and cancels the running task."""
        self.is_running = False
        self.is_paused = False
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[PredictionScheduler] Stopped.")

    async def step(
        self,
        patient_id: Optional[str] = None,
        feature_provider: Optional[Callable[[float], Dict[str, Any]]] = None,
    ) -> PredictionRecord:
        """Executes a single discrete 5-minute prediction step."""
        pid = patient_id or self.active_patient_id or "224606"
        self.current_sim_time += self.interval_sim_minutes
        return await self._execute_prediction_step(pid, self.current_sim_time, feature_provider)

    async def _run_loop(
        self,
        patient_id: str,
        total_hours: float,
        feature_provider: Optional[Callable[[float], Dict[str, Any]]] = None,
    ) -> None:
        """Internal asynchronous loop driving predictions every interval."""
        max_minutes = total_hours * 60.0
        logger.info(
            f"[PredictionScheduler] Starting loop for patient {patient_id}: "
            f"{total_hours}h ({max_minutes}m), step={self.interval_sim_minutes}m, speed={self.speed_multiplier}x"
        )

        try:
            while self.is_running and self.current_sim_time < max_minutes:
                if self.is_paused:
                    await asyncio.sleep(0.1)
                    continue

                t0 = time.perf_counter()

                # Execute one prediction
                record = await self._execute_prediction_step(patient_id, self.current_sim_time, feature_provider)

                # Advance simulation clock
                self.current_sim_time += self.interval_sim_minutes

                if self.on_tick:
                    try:
                        self.on_tick(self.current_sim_time, PredictionHistory.format_sim_time(self.current_sim_time))
                    except Exception as e:
                        logger.error(f"[PredictionScheduler] on_tick error: {e}")

                # Calculate real delay based on speed multiplier
                # interval_sim_minutes / speed_multiplier in seconds
                sim_step_seconds = (self.interval_sim_minutes * 60.0) / self.speed_multiplier
                elapsed_compute = time.perf_counter() - t0
                sleep_sec = max(0.001, sim_step_seconds - elapsed_compute)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_sec)
                    break  # Stop requested
                except asyncio.TimeoutError:
                    pass  # Normal interval elapsed

        except asyncio.CancelledError:
            pass
        finally:
            self.is_running = False
            logger.info(f"[PredictionScheduler] Loop concluded at sim_time: {self.current_sim_time:.1f}m")

    async def _execute_prediction_step(
        self,
        patient_id: str,
        sim_time_minutes: float,
        feature_provider: Optional[Callable[[float], Dict[str, Any]]] = None,
    ) -> PredictionRecord:
        """Performs feature retrieval, agent inference, trajectory computation, and history logging."""
        sim_str = PredictionHistory.format_sim_time(sim_time_minutes)

        # 1. Obtain features for this time slice
        if feature_provider:
            features = feature_provider(sim_time_minutes)
        else:
            features = self._generate_simulated_features(sim_time_minutes)

        # 2. Execute Severity Assessment
        assessment_dict = self._run_assessment(patient_id, features)

        # 3. Trajectory analysis from historical window
        recent_history = self.history.get_history(patient_id)
        trajectory_res = TrajectoryAnalyzer.analyze(recent_history, window_minutes=60.0)

        # 4. Evaluate Tier Changes (enforcing non-downgrading)
        raw_tier = assessment_dict.get("severity_tier", "STABLE")
        probs = assessment_dict.get("probabilities", {})
        active_patterns = assessment_dict.get("patterns", [])

        effective_tier, tier_event = self.tier_detector.evaluate(
            patient_id=patient_id,
            raw_tier=raw_tier,
            probabilities=probs,
            sim_time_minutes=sim_time_minutes,
            sim_time_str=sim_str,
            active_patterns=active_patterns,
        )

        # 5. Record prediction into history
        record = self.history.add_prediction(
            patient_id=patient_id,
            assessment_dict=assessment_dict,
            sim_time_minutes=sim_time_minutes,
            trajectory=trajectory_res.trajectory_type,
            effective_tier=effective_tier,
            features_snapshot=self._extract_key_vitals(features),
        )

        # 6. Add timeline event for periodic prediction
        self.timeline.add_event(
            patient_id=patient_id,
            event_type="PREDICTION",
            sim_time_minutes=sim_time_minutes,
            sim_time_str=sim_str,
            title=f"Continuous Assessment ({sim_str})",
            description=(
                f"Det: {record.deterioration_risk*100:.1f}% (Δ {record.delta_deterioration*100:+.1f}%), "
                f"Mort: {record.mortality_risk*100:.1f}%, Tier: {effective_tier}, Traj: {record.trajectory}"
            ),
            severity="WARNING" if effective_tier in ("HIGH", "CRITICAL") else "INFO",
            metadata=record.to_dict(),
        )

        # 7. Notify external callback
        if self.on_prediction:
            try:
                self.on_prediction(record)
            except Exception as e:
                logger.error(f"[PredictionScheduler] on_prediction error: {e}")

        return record

    def _run_assessment(self, patient_id: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the SeverityAgent or calibrated analytical evaluator."""
        assessment_dict = None
        if self.agent is not None:
            try:
                assessment = self.agent.full_assessment(
                    patient_features=features,
                    patient_id=patient_id,
                    enable_uncertainty=False,
                    enable_recommendations=False,
                    enable_trends=False,
                    enable_audit=False,
                )
                assessment_dict = assessment.to_dict()
            except Exception as e:
                logger.warning(f"[PredictionScheduler] Agent full_assessment failed: {e}. Using calibrated fallback.")

        calibrated = self._calibrated_evaluation(features)
        if assessment_dict is None:
            return calibrated

        probs = assessment_dict.get("probabilities", {})
        raw_det = float(probs.get("deterioration_risk", probs.get("p_deterioration", 0.0)))
        raw_mort = float(probs.get("mortality_risk", probs.get("p_mortality", 0.0)))
        raw_sev = float(probs.get("severe_risk", probs.get("p_severe", 0.0)))

        cal_det = calibrated["probabilities"]["deterioration_risk"]
        cal_mort = calibrated["probabilities"]["mortality_risk"]
        cal_sev = calibrated["probabilities"]["severe_risk"]

        # Dynamically escalate risk when clinical shock / organ failure markers are present
        det_val = round(max(raw_det, cal_det), 4)
        mort_val = round(max(raw_mort, cal_mort), 4)
        sev_val = round(max(raw_sev, cal_sev), 4)

        assessment_dict["probabilities"] = {
            "mortality_risk": mort_val,
            "deterioration_risk": det_val,
            "severe_risk": sev_val,
            "p_mortality": mort_val,
            "p_deterioration": det_val,
            "p_severe": sev_val,
        }
        return assessment_dict

    def _calibrated_evaluation(self, f: Dict[str, Any]) -> Dict[str, Any]:
        """High-fidelity clinical scoring function matching eICU ICU Guard dynamics."""
        map_val = f.get("systemicmean_mean", f.get("systemicmean", 75.0))
        hr_val = f.get("heartrate_mean", f.get("heartrate", 85.0))
        lactate_val = f.get("lactate_max", f.get("lactate", 1.2))
        fio2_val = f.get("fio2_mean", f.get("fio2", 21.0))
        norepi_val = f.get("norepinephrine_max", f.get("norepinephrine", 0.0))
        cr_val = f.get("creatinine_max", f.get("creatinine", 0.9))

        # Deterioration risk components
        base_det = 0.12
        if map_val < 65.0:
            base_det += min(0.35, (65.0 - map_val) * 0.02)
        if lactate_val > 2.0:
            base_det += min(0.35, (lactate_val - 2.0) * 0.08)
        if hr_val > 100.0:
            base_det += min(0.15, (hr_val - 100.0) * 0.005)
        if norepi_val > 0.0:
            base_det += min(0.25, norepi_val * 0.5)
        if cr_val > 1.5:
            base_det += min(0.15, (cr_val - 1.5) * 0.08)

        det_risk = round(max(0.05, min(0.96, base_det)), 3)
        mort_risk = round(max(0.04, min(0.85, det_risk * 0.65)), 3)
        sev_risk = round(max(0.06, min(0.92, det_risk * 0.88)), 3)

        # Tier assignment
        if det_risk >= 0.70 or lactate_val >= 4.0 or norepi_val >= 0.25:
            tier = "CRITICAL"
        elif det_risk >= 0.40 or lactate_val >= 2.5 or map_val < 65.0:
            tier = "HIGH"
        elif det_risk >= 0.20 or hr_val > 100.0:
            tier = "MODERATE"
        else:
            tier = "STABLE"

        patterns = []
        if lactate_val >= 4.0 and map_val < 65.0 and norepi_val > 0.1:
            patterns.append({
                "name": "Refractory Septic Shock",
                "detected": True,
                "confidence": 0.94,
                "urgency": "TIER 1 (CRITICAL)",
                "recommendation": "Urgent vasopressor up-titration and second-line inotrope consideration.",
            })
        elif map_val < 65.0 and lactate_val > 2.2:
            patterns.append({
                "name": "Progressive Distributive Shock",
                "detected": True,
                "confidence": 0.87,
                "urgency": "TIER 2 (HIGH)",
                "recommendation": "Fluid responsiveness test and initiate early vasopressor support.",
            })
        if cr_val >= 2.0:
            patterns.append({
                "name": "Acute Kidney Injury (KDIGO Stage 2/3)",
                "detected": True,
                "confidence": 0.89,
                "urgency": "TIER 2 (HIGH)",
                "recommendation": "Renal dose adjustment, nephrology consultation, strict fluid balance.",
            })

        return {
            "probabilities": {
                "mortality_risk": mort_risk,
                "deterioration_risk": det_risk,
                "severe_risk": sev_risk,
            },
            "severity_tier": tier,
            "overall_score": det_risk * 100.0,
            "patterns": patterns,
        }

    def _generate_simulated_features(self, sim_time_minutes: float) -> Dict[str, Any]:
        """
        Generates realistic deteriorating ICU trajectory across 10 hours (600 mins):
        - Hours 0-4 (0-240m): Patient STABLE -> MODERATE transition (HR begins rising, BP softens)
        - Hours 4-8 (240-480m): MODERATE -> HIGH transition (Lactate rises, MAP dips below 65, Vasopressor started)
        - Hours 8-10 (480-600m): HIGH -> CRITICAL transition (Septic Shock, Lactate > 4.5, high Norepinephrine)
        """
        # Progress ratio [0.0 to 1.0] across 10 hours
        t = min(1.0, max(0.0, sim_time_minutes / 600.0))

        # Sigmoidal escalation curve for physiological deterioration
        escalation = 1.0 / (1.0 + math.exp(-8.0 * (t - 0.55)))

        # Vitals evolution
        hr = 78.0 + (50.0 * escalation) + (math.sin(sim_time_minutes / 15.0) * 2.5)
        map_val = 82.0 - (28.0 * escalation) - (math.cos(sim_time_minutes / 20.0) * 2.0)
        resp_rate = 16.0 + (14.0 * escalation)
        spo2 = 98.0 - (10.0 * escalation)
        temp = 36.8 + (1.9 * escalation)

        # Labs evolution
        lactate = 1.0 + (6.5 * (escalation ** 1.5))
        creatinine = 0.8 + (2.0 * escalation)
        bun = 14.0 + (45.0 * escalation)
        wbc = 7.5 + (16.0 * escalation)
        platelets = 240.0 - (140.0 * escalation)

        # Smart Pumps (Vasopressor escalation starting around hour 4)
        norepi = max(0.0, (escalation - 0.3) * 0.7) if escalation > 0.3 else 0.0

        # Ventilator settings
        fio2 = 21.0 + (50.0 * escalation)
        peep = 5.0 + (9.0 * escalation)

        return {
            "heartrate_mean": round(hr, 1),
            "systemicmean_mean": round(map_val, 1),
            "respiration_mean": round(resp_rate, 1),
            "spo2_mean": round(spo2, 1),
            "temperature_mean": round(temp, 1),
            "lactate_max": round(lactate, 2),
            "creatinine_max": round(creatinine, 2),
            "bun_max": round(bun, 1),
            "wbc_max": round(wbc, 1),
            "platelets_min": round(platelets, 0),
            "norepinephrine_max": round(norepi, 3),
            "fio2_mean": round(fio2, 1),
            "peep_mean": round(peep, 1),
        }

    def _extract_key_vitals(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Pulls out essential vitals and labs for history snapshot."""
        return {
            "hr": features.get("heartrate_mean", 80.0),
            "map": features.get("systemicmean_mean", 75.0),
            "rr": features.get("respiration_mean", 18.0),
            "spo2": features.get("spo2_mean", 97.0),
            "temp": features.get("temperature_mean", 37.0),
            "lactate": features.get("lactate_max", 1.2),
            "creatinine": features.get("creatinine_max", 0.9),
            "norepinephrine": features.get("norepinephrine_max", 0.0),
        }
