"""
base_device.py — Abstract Base Class for Medical Device Simulators
==================================================================
Provides standardized lifecycle, reading capture, HL7 formatting,
and asynchronous streaming capabilities for ICU bedside devices.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import random
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from ..core.message_builder import HL7Message
from ..core.mllp_server import MLLPClient

logger = logging.getLogger("hl7_simulator.device")


class BaseDevice(abc.ABC):
    """
    Abstract base class for all simulated medical devices in ICU Guard.

    Attributes:
        device_id: Unique hardware identifier or serial number
        device_name: Clinical device model (e.g., 'PHILIPS_INTELLIVUE')
        bed_id: ICU bed identifier (e.g., 'ICU_BED_04')
        patient_id: Identifier of the patient currently admitted
    """

    def __init__(
        self,
        device_id: str,
        device_name: str,
        bed_id: str = "ICU_BED_01",
        patient_id: str = "224606",
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.bed_id = bed_id
        self.patient_id = patient_id
        self.is_connected = False
        self._client: Optional[MLLPClient] = None

    def connect(self, host: str = "127.0.0.1", port: int = 6661, timeout: float = 5.0) -> None:
        """Initialize connection to integration engine / MLLP server."""
        self._client = MLLPClient(host=host, port=port, timeout=timeout)
        self.is_connected = True
        logger.info(f"[{self.device_name}] Connected to MLLP at {host}:{port} for {self.bed_id}")

    def disconnect(self) -> None:
        """Terminate connection."""
        self.is_connected = False
        self._client = None
        logger.info(f"[{self.device_name}] Disconnected from bed {self.bed_id}")

    @abc.abstractmethod
    def get_readings(self, progress: float = 0.0) -> Dict[str, float]:
        """
        Produce a dictionary of current physiological measurements.

        Args:
            progress: Normalized timeline progress from 0.0 (start) to 1.0 (end of scenario).
        """
        pass

    @abc.abstractmethod
    def to_hl7(self, readings: Dict[str, float], timestamp: Optional[datetime] = None) -> HL7Message:
        """Format current device readings into an HL7 v2.5 ORU^R01 message."""
        pass

    async def stream(
        self,
        duration_minutes: float = 360.0,
        interval_seconds: float = 30.0,
        time_dilation: float = 1.0,
    ) -> AsyncGenerator[tuple[HL7Message, Optional[str]], None]:
        """
        Asynchronously stream telemetry readings over time.

        Args:
            duration_minutes: Total simulated clinical observation window (e.g., 6 hours = 360 min)
            interval_seconds: Real or accelerated interval between transmission ticks
            time_dilation: Multiplier for accelerating time in simulations (1.0 = real time)

        Yields:
            (HL7Message, optional_ack_response)
        """
        total_seconds = duration_minutes * 60.0
        elapsed_sim_seconds = 0.0
        tick_delay = max(0.001, interval_seconds / time_dilation)

        logger.info(
            f"[{self.device_name}] Starting stream on {self.bed_id}: "
            f"Duration={duration_minutes}m, Interval={interval_seconds}s, Dilation={time_dilation}x"
        )

        while elapsed_sim_seconds <= total_seconds:
            progress = min(1.0, elapsed_sim_seconds / total_seconds if total_seconds > 0 else 1.0)
            readings = self.get_readings(progress=progress)
            msg = self.to_hl7(readings)

            ack: Optional[str] = None
            if self.is_connected and self._client:
                try:
                    ack = await self._client.send_message(msg.to_string())
                except Exception as e:
                    logger.warning(f"[{self.device_name}] Failed to send via MLLP: {e}")

            yield msg, ack

            if elapsed_sim_seconds >= total_seconds:
                break

            await asyncio.sleep(tick_delay)
            elapsed_sim_seconds += interval_seconds

    @staticmethod
    def apply_physiological_noise(value: float, std_percent: float = 0.015) -> float:
        """Add realistic Gaussian micro-variation to simulate sensor/beat noise."""
        noise = random.gauss(0, value * std_percent)
        return value + noise

    @staticmethod
    def linear_interpolate(start_val: float, end_val: float, progress: float) -> float:
        """Smoothly interpolate value between start and end according to progress (0.0 to 1.0)."""
        clamped_p = max(0.0, min(1.0, progress))
        return start_val + (end_val - start_val) * clamped_p
