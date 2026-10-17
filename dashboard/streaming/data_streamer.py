"""
ICU Guard v5.0 — Real-Time Telemetry Data Streamer
Generates and streams continuous high-frequency vital signs and physiological
signals for any eICU patient cohort archetype at configurable clinical speeds.
"""

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, AsyncIterator, Callable


@dataclass
class StreamFrame:
    """Represents a single time tick of streamed patient telemetry."""
    tick: int
    total_ticks: int
    progress_pct: float
    timestamp_str: str
    vitals: Dict[str, float]
    full_features: Dict[str, Any]
    is_terminal: bool = False


class DataStreamer:
    """
    Manages asynchronous temporal playback of patient ICU data.
    Provides pause, resume, stop, and multi-speed telemetry (1x, 5x, 10x, 50x).
    """

    SPEED_DELAYS = {
        1.0: 1.0,     # 1x: 1000ms per tick
        5.0: 0.2,     # 5x: 200ms per tick
        10.0: 0.1,    # 10x: 100ms per tick
        50.0: 0.02,   # 50x: 20ms per tick
    }

    def __init__(
        self,
        patient_record: Dict[str, Any],
        total_ticks: int = 60,
        speed: float = 1.0,
        on_tick: Optional[Callable[[StreamFrame], Any]] = None,
        on_complete: Optional[Callable[[], Any]] = None,
    ):
        self.patient_record = patient_record.copy()
        self.total_ticks = max(total_ticks, 1)
        self.speed = speed
        self.current_tick = 0
        self.is_paused = False
        self.is_stopped = False
        self.is_running = False

        self.on_tick = on_tick
        self.on_complete = on_complete

        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Unpaused initially

        # Synthesize realistic continuous time-series curves
        self._series: List[Dict[str, float]] = self._generate_trajectory_series()

    def _safe_float(self, val: Any, default: float) -> float:
        try:
            if val is None:
                return default
            f = float(val)
            return default if math.isnan(f) else f
        except Exception:
            return default

    def _generate_trajectory_series(self) -> List[Dict[str, float]]:
        """
        Synthesizes a realistic autoregressive physiological trajectory
        anchored on the patient's actual baseline and peak/nadir clinical features.
        """
        p = self.patient_record
        tier = str(p.get("tier", "STABLE")).upper()

        # Target Extremes from Real eICU Record
        hr_mean = self._safe_float(p.get("heartrate_mean"), 78.0)
        hr_max = self._safe_float(p.get("heartrate_max"), hr_mean + 10.0)
        mbp_min = self._safe_float(p.get("meanbp_min"), 75.0)
        sbp_min = self._safe_float(p.get("sbp_min"), mbp_min * 1.35)
        rr_max = self._safe_float(p.get("resprate_max"), 18.0)
        temp_max = self._safe_float(p.get("temperature_max"), 37.0)
        sao2_min = self._safe_float(p.get("sao2_min"), 98.0)
        gcs_min = self._safe_float(p.get("gcs_min"), 15.0)
        lactate_max = self._safe_float(p.get("lactate_max"), 1.2)

        # Baseline starting values
        if tier in {"CRITICAL", "HIGH"}:
            # Patient starts somewhat decompensated, then plunges towards extreme shock
            hr_curr = hr_mean * 0.95
            mbp_curr = mbp_min * 1.3
            sbp_curr = sbp_min * 1.3
            rr_curr = max(rr_max * 0.75, 18.0)
            temp_curr = (temp_max + 37.0) / 2.0
            sao2_curr = min(sao2_min + 7.0, 99.0)
            gcs_curr = min(gcs_min + 3.0, 15.0)
            lac_curr = max(lactate_max * 0.5, 1.4)
        else:
            # Stable patient stays in physiologic equilibrium
            hr_curr = hr_mean
            mbp_curr = max(mbp_min, 75.0)
            sbp_curr = max(sbp_min, 115.0)
            rr_curr = min(rr_max, 16.0)
            temp_curr = 36.8
            sao2_curr = max(sao2_min, 97.0)
            gcs_curr = 15.0
            lac_curr = min(lactate_max, 1.3)

        series: List[Dict[str, float]] = []

        for t in range(self.total_ticks):
            progress = t / max(self.total_ticks - 1, 1)

            if tier in {"CRITICAL", "HIGH"}:
                # Nonlinear deterioration curve (Sigmoidal or worsening trajectory)
                factor = 1.0 / (1.0 + math.exp(-6.0 * (progress - 0.45)))
                target_hr = hr_curr + factor * (hr_max - hr_curr)
                target_mbp = mbp_curr - factor * (mbp_curr - mbp_min)
                target_sbp = sbp_curr - factor * (sbp_curr - sbp_min)
                target_rr = rr_curr + factor * (rr_max - rr_curr)
                target_sao2 = sao2_curr - factor * (sao2_curr - sao2_min)
                target_temp = temp_curr + factor * (temp_max - temp_curr)
                target_gcs = gcs_curr - factor * (gcs_curr - gcs_min)
                target_lac = lac_curr + factor * (lactate_max - lac_curr)
            else:
                # Stable circadian fluctuation
                sin_wave = math.sin(t * 0.3)
                target_hr = hr_curr + sin_wave * 3.0
                target_mbp = mbp_curr + sin_wave * 2.5
                target_sbp = sbp_curr + sin_wave * 3.5
                target_rr = rr_curr + sin_wave * 1.0
                target_sao2 = 98.0 + sin_wave * 0.8
                target_temp = 36.8 + sin_wave * 0.15
                target_gcs = 15.0
                target_lac = 1.1 + sin_wave * 0.1

            # Autoregressive smoothing with realistic physiological jitter
            jitter_hr = random.gauss(0, 1.2)
            jitter_bp = random.gauss(0, 1.5)
            jitter_rr = random.gauss(0, 0.6)
            jitter_o2 = random.gauss(0, 0.4)
            jitter_temp = random.gauss(0, 0.05)

            step_hr = max(35.0, min(220.0, target_hr + jitter_hr))
            step_mbp = max(30.0, min(160.0, target_mbp + jitter_bp))
            step_sbp = max(50.0, min(240.0, target_sbp + jitter_bp * 1.2))
            step_rr = max(6.0, min(55.0, target_rr + jitter_rr))
            step_sao2 = max(65.0, min(100.0, target_sao2 + jitter_o2))
            step_temp = max(34.0, min(42.0, target_temp + jitter_temp))
            step_gcs = max(3.0, min(15.0, round(target_gcs)))
            step_lac = max(0.5, min(20.0, target_lac + random.gauss(0, 0.08)))

            series.append({
                "hr": round(step_hr, 1),
                "sbp": round(step_sbp, 1),
                "map": round(step_mbp, 1),
                "dbp": round(max(step_mbp * 2 - step_sbp * 0.8, 30.0), 1),
                "rr": round(step_rr, 1),
                "temp": round(step_temp, 2),
                "sao2": round(step_sao2, 1),
                "gcs": float(step_gcs),
                "lactate": round(step_lac, 2),
            })

        return series

    def set_speed(self, speed: float) -> None:
        """Dynamically adjusts playback speed (1x, 5x, 10x, 50x)."""
        if speed in self.SPEED_DELAYS:
            self.speed = speed
        elif speed > 0:
            self.speed = speed

    def pause(self) -> None:
        """Pauses data streaming."""
        self.is_paused = True
        self._pause_event.clear()

    def resume(self) -> None:
        """Resumes data streaming."""
        self.is_paused = False
        self._pause_event.set()

    def stop(self) -> None:
        """Stops streaming and marks as terminal."""
        self.is_stopped = True
        self.is_running = False
        self._pause_event.set()

    def restart(self) -> None:
        """Resets playback to tick 0."""
        self.current_tick = 0
        self.is_stopped = False
        self.is_paused = False
        self._pause_event.set()

    async def run_loop(self) -> None:
        """Async streaming loop that fires callbacks at each time tick."""
        self.is_running = True
        self.is_stopped = False
        base_time = datetime.now()

        while self.current_tick < self.total_ticks and not self.is_stopped:
            # Respect pause state
            await self._pause_event.wait()
            if self.is_stopped:
                break

            current_vitals = self._series[self.current_tick]
            tick_time = base_time + timedelta(seconds=self.current_tick * 60)
            time_str = tick_time.strftime("%H:%M:%S")

            # Update working features dict with instantaneous readings
            updated_features = self.patient_record.copy()
            updated_features.update({
                "heartrate_mean": current_vitals["hr"],
                "heartrate_max": max(current_vitals["hr"], self._safe_float(self.patient_record.get("heartrate_max"), 0)),
                "meanbp_min": current_vitals["map"],
                "sbp_min": current_vitals["sbp"],
                "shock_index_max": current_vitals["hr"] / max(current_vitals["sbp"], 40.0),
                "resprate_max": current_vitals["rr"],
                "sao2_min": current_vitals["sao2"],
                "temperature_max": current_vitals["temp"],
                "gcs_min": current_vitals["gcs"],
                "lactate_max": current_vitals["lactate"],
            })

            is_terminal = (self.current_tick == self.total_ticks - 1)
            progress_pct = ((self.current_tick + 1) / self.total_ticks) * 100.0

            frame = StreamFrame(
                tick=self.current_tick + 1,
                total_ticks=self.total_ticks,
                progress_pct=progress_pct,
                timestamp_str=time_str,
                vitals=current_vitals,
                full_features=updated_features,
                is_terminal=is_terminal,
            )

            if self.on_tick:
                try:
                    res = self.on_tick(frame)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    import logging
                    logging.getLogger("icu_guard.streamer").error("Telemetry tick error: %s", e, exc_info=True)

            self.current_tick += 1

            if is_terminal:
                break

            delay = self.SPEED_DELAYS.get(self.speed, 1.0 / max(self.speed, 1.0))
            await asyncio.sleep(delay)

        self.is_running = False
        if not self.is_stopped and self.on_complete:
            try:
                res = self.on_complete()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
