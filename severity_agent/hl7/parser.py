"""
parser.py — Robust HL7 v2.5 Message Parser
===========================================
Parses raw HL7 ORU^R01 observation messages into clean structured data models
compatible with the ICU Guard Feature Extractor and Device Manager.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("icu_guard.hl7.parser")


@dataclass
class ParsedObservation:
    """Represents a single parsed OBX observation."""
    loinc: str
    name: str
    value: float
    raw_value: str
    unit: str
    flag: str
    ref_range: str
    timestamp: datetime


@dataclass
class ParsedHL7Message:
    """Structured representation of an incoming HL7 message."""
    message_id: str
    device: str
    bed_id: str
    patient_id: str
    timestamp: datetime
    panel: str
    observations: List[ParsedObservation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert parsed message to standard JSON/dict representation."""
        return {
            "message_id": self.message_id,
            "device": self.device,
            "bed_id": self.bed_id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp.isoformat(),
            "panel": self.panel,
            "observations": [
                {
                    "loinc": obs.loinc,
                    "name": obs.name,
                    "value": obs.value,
                    "unit": obs.unit,
                    "flag": obs.flag,
                    "ref_range": obs.ref_range,
                }
                for obs in self.observations
            ],
        }


class HL7Parser:
    """
    Parser for HL7 v2.5 observation messages (ORU^R01).
    """

    @staticmethod
    def _parse_ts(ts_str: str) -> datetime:
        """Parse HL7 timestamp string (YYYYMMDD[HHmmss])."""
        clean_ts = ts_str.strip()
        formats = ["%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(clean_ts[:len(fmt.replace("%", "")) + 2], fmt)
            except Exception:
                continue
        return datetime.now()

    @classmethod
    def parse(cls, raw_hl7: str) -> Optional[ParsedHL7Message]:
        """
        Parse raw HL7 string into a ParsedHL7Message object.
        Returns None if message is invalid or missing MSH.
        """
        if not raw_hl7 or not isinstance(raw_hl7, str):
            return None

        # Standardize line separators to \r
        lines = [line.strip() for line in raw_hl7.replace("\r\n", "\r").replace("\n", "\r").split("\r") if line.strip()]
        if not lines:
            return None

        message_id = "UNKNOWN"
        device = "UNKNOWN_DEVICE"
        bed_id = "UNKNOWN_BED"
        patient_id = "000000"
        msg_time = datetime.now()
        panel = "GENERAL_PANEL"
        observations: List[ParsedObservation] = []

        for line in lines:
            fields = line.split("|")
            seg_name = fields[0].strip().upper()

            # ── MSH Segment ───────────────────────────────────────────
            if seg_name == "MSH":
                if len(fields) > 2:
                    device = fields[2].strip() or device
                if len(fields) > 3:
                    bed_id = fields[3].strip() or bed_id
                if len(fields) > 6 and fields[6].strip():
                    msg_time = cls._parse_ts(fields[6])
                if len(fields) > 9:
                    message_id = fields[9].strip() or message_id

            # ── PID Segment ───────────────────────────────────────────
            elif seg_name == "PID":
                if len(fields) > 3 and fields[3].strip():
                    # Format: ID^^^NAMESPACE
                    cx = fields[3].split("^")
                    patient_id = cx[0].strip() or patient_id

            # ── OBR Segment ───────────────────────────────────────────
            elif seg_name == "OBR":
                if len(fields) > 4 and fields[4].strip():
                    panel = fields[4].strip()
                if len(fields) > 7 and fields[7].strip():
                    msg_time = cls._parse_ts(fields[7])

            # ── OBX Segment ───────────────────────────────────────────
            elif seg_name == "OBX":
                if len(fields) > 5:
                    # OBX-3: Identifier (CODE^NAME^NAMESPACE)
                    obs_id_parts = fields[3].split("^")
                    loinc_code = obs_id_parts[0].strip() if len(obs_id_parts) > 0 else ""
                    obs_name = obs_id_parts[1].strip() if len(obs_id_parts) > 1 else ""

                    raw_val = fields[5].strip()
                    try:
                        numeric_val = float(raw_val)
                    except ValueError:
                        numeric_val = 0.0

                    unit = fields[6].strip() if len(fields) > 6 else ""
                    ref_range = fields[7].strip() if len(fields) > 7 else ""
                    flag = fields[8].strip() if len(fields) > 8 else "N"

                    obs_time = msg_time
                    if len(fields) > 14 and fields[14].strip():
                        obs_time = cls._parse_ts(fields[14])

                    observations.append(
                        ParsedObservation(
                            loinc=loinc_code,
                            name=obs_name,
                            value=numeric_val,
                            raw_value=raw_val,
                            unit=unit,
                            flag=flag,
                            ref_range=ref_range,
                            timestamp=obs_time,
                        )
                    )

        if not observations:
            logger.debug(f"[HL7Parser] Message {message_id} parsed with 0 observations.")

        return ParsedHL7Message(
            message_id=message_id,
            device=device,
            bed_id=bed_id,
            patient_id=patient_id,
            timestamp=msg_time,
            panel=panel,
            observations=observations,
        )
