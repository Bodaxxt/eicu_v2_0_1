"""
device_manager.py — Multi-Device Bedside Telemetry Manager
===========================================================
Tracks operational status, communication latency, message volume,
and patient assignments across all 5 ICU medical device modalities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .parser import ParsedHL7Message
from .buffer import PatientDataBuffer

logger = logging.getLogger("icu_guard.hl7.devices")


@dataclass
class DeviceStatus:
    """Real-time connectivity and throughput statistics for a medical device."""
    device_id: str
    device_type: str         # "monitor" | "abg" | "lab" | "pumps" | "ventilator"
    bed_id: str
    patient_id: str
    is_active: bool = True
    messages_received: int = 0
    last_seen: Optional[datetime] = None
    last_error: Optional[str] = None
    last_observations: Dict[str, float] = field(default_factory=dict)


class DeviceManager:
    """
    Coordinates bedside telemetry across all 5 device modalities.
    """

    DEVICE_TYPE_MAP = {
        "PHILIPS_INTELLIVUE": "monitor",
        "GE_CARESCAPE": "monitor",
        "MINDRAY_BENEVISION": "monitor",
        "RADIOMETER_ABL800": "abg",
        "ROCHE_COBAS_B123": "abg",
        "IL_GEM_PREMIER": "abg",
        "ROCHE_COBAS_8000": "lab",
        "ABBOTT_ARCHITECT": "lab",
        "SIEMENS_ATELLICA": "lab",
        "BBRAUN_SPACE": "pumps",
        "BD_ALARIS": "pumps",
        "FRESENIUS_AGILIA": "pumps",
        "DRAEGER_EVITA": "ventilator",
        "HAMILTON_MEDICAL": "ventilator",
        "PURITAN_BENNETT_980": "ventilator",
    }

    def __init__(self):
        # device_id -> DeviceStatus
        self._devices: Dict[str, DeviceStatus] = {}
        # patient_id -> PatientDataBuffer
        self._buffers: Dict[str, PatientDataBuffer] = {}
        # bed_id -> active patient_id
        self._bed_to_patient: Dict[str, str] = {}

    def get_or_create_buffer(self, patient_id: str) -> PatientDataBuffer:
        """Retrieve existing patient buffer or allocate a new one."""
        if patient_id not in self._buffers:
            self._buffers[patient_id] = PatientDataBuffer(patient_id=patient_id)
            logger.info(f"[DeviceManager] Allocated new PatientDataBuffer for patient {patient_id}")
        return self._buffers[patient_id]

    def process_message(self, msg: ParsedHL7Message) -> PatientDataBuffer:
        """
        Record incoming device telemetry, update device health, and buffer observations.
        """
        # Determine device classification
        dev_name = msg.device.upper()
        dev_type = "unknown"
        for key, val in self.DEVICE_TYPE_MAP.items():
            if key in dev_name:
                dev_type = val
                break

        # Register or update device record
        if msg.device not in self._devices:
            self._devices[msg.device] = DeviceStatus(
                device_id=msg.device,
                device_type=dev_type,
                bed_id=msg.bed_id,
                patient_id=msg.patient_id,
            )

        status = self._devices[msg.device]
        status.messages_received += 1
        status.last_seen = msg.timestamp
        status.is_active = True
        status.bed_id = msg.bed_id
        status.patient_id = msg.patient_id

        # Update latest readings snapshot
        for obs in msg.observations:
            status.last_observations[obs.name or obs.loinc] = obs.value

        # Track bed to patient
        if msg.bed_id and msg.patient_id:
            self._bed_to_patient[msg.bed_id] = msg.patient_id

        # Ingest into patient buffer
        buffer = self.get_or_create_buffer(msg.patient_id)
        buffer.add_message(msg)
        return buffer

    def get_device_status(self, device_id: str) -> Optional[DeviceStatus]:
        """Return status for a specific device."""
        return self._devices.get(device_id)

    def get_all_devices(self) -> List[DeviceStatus]:
        """List all active and registered devices."""
        return list(self._devices.values())

    def get_patient_for_bed(self, bed_id: str) -> Optional[str]:
        """Lookup active patient ID currently assigned to a bed."""
        return self._bed_to_patient.get(bed_id)
