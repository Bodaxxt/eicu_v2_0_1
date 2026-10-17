"""
message_builder.py — HL7 v2.5 ORU^R01 Message Builder
=======================================================
High-level API for constructing complete HL7 messages
from individual observations.

Typical usage:
    from hl7_simulator.core import HL7MessageBuilder, LOINC

    msg = (
        HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04")
        .add_observation(LOINC.HEART_RATE, 112.0)
        .add_observation(LOINC.MEAN_BP,     46.0)
        .add_observation(LOINC.OXYGEN_SAT,  84.0)
        .build()
    )
    print(msg.to_string())
    print(msg.to_mllp())
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime    import datetime
from typing      import List, Optional

from .loinc_codes import LOINCCode, LOINC
from .segments    import MSH, PID, OBR, OBX, AbnormalFlag, FIELD_SEP


# ─────────────────────────────────────────────────────────────────────────────
# MLLP framing constants (RFC / HL7 MLLP spec)
# ─────────────────────────────────────────────────────────────────────────────
MLLP_START  = "\x0b"   # VT  — Vertical Tab (start of block)
MLLP_END    = "\x1c"   # FS  — File Separator (end of block)
MLLP_CR     = "\r"     # CR  — Carriage Return (after FS)
SEGMENT_SEP = "\r"     # HL7 segment separator


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ObservationResult:
    """A single numeric observation ready to render as an OBX segment."""
    loinc_code     : LOINCCode
    value          : float
    abnormal_flag  : AbnormalFlag
    observation_time: datetime = field(default_factory=datetime.now)

    @property
    def reference_range(self) -> str:
        if self.loinc_code.normal_low is not None and self.loinc_code.normal_high is not None:
            return f"{self.loinc_code.normal_low}-{self.loinc_code.normal_high}"
        return ""


@dataclass
class HL7Message:
    """
    A fully assembled HL7 v2.5 ORU^R01 message.

    Attributes:
        message_id   : Unique message control ID
        segments     : Ordered list of segment strings
        raw_string   : The complete HL7 message as a pipe-delimited string
    """
    message_id   : str
    segments     : List[str]
    observations : List[ObservationResult]
    _raw         : str = field(init=False, repr=False)

    def __post_init__(self):
        self._raw = SEGMENT_SEP.join(self.segments)

    def to_string(self) -> str:
        """Return the HL7 message as a human-readable pipe-delimited string."""
        return self._raw

    def to_mllp(self) -> bytes:
        """
        Wrap the HL7 message in MLLP framing for TCP transmission.

        Frame structure:
            VT  (0x0B)  — Start block
            <HL7 message>
            FS  (0x1C)  — End of block
            CR  (0x0D)  — Carriage return
        """
        wrapped = f"{MLLP_START}{self._raw}{MLLP_END}{MLLP_CR}"
        return wrapped.encode("utf-8")

    def summary(self) -> str:
        """Return a compact human-readable summary for logging."""
        lines = [f"[HL7 Message {self.message_id}]"]
        for obs in self.observations:
            flag = obs.abnormal_flag.value
            lines.append(
                f"  {obs.loinc_code.code:<10} "
                f"{obs.loinc_code.display_name:<20} "
                f"{obs.value:>8.2f} {obs.loinc_code.unit:<12} "
                f"[{flag}]"
            )
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────

class HL7MessageBuilder:
    """
    Fluent builder for HL7 v2.5 ORU^R01 messages.

    The builder accumulates observations via add_observation() calls,
    then assembles the complete message with build().

    Args:
        patient_id          : Patient unit stay ID (eICU patientunitstayid)
        bed_id              : ICU bed identifier (e.g. 'ICU_BED_04')
        sending_application : Source device application name
        sending_facility    : Source device physical location
        panel_id            : OBR panel identifier (defaults to device type)
        timestamp           : Message timestamp (defaults to now)

    Example:
        builder = HL7MessageBuilder(
            patient_id="224606",
            bed_id="ICU_BED_04",
            sending_application="PHILIPS_INTELLIVUE",
        )
        builder.add_observation(LOINC.HEART_RATE, 112.0)
        builder.add_observation(LOINC.MEAN_BP,     46.0)
        msg = builder.build()
    """

    def __init__(
        self,
        patient_id           : str  = "000000",
        bed_id               : str  = "ICU_BED_01",
        sending_application  : str  = "DEVICE_SIMULATOR",
        sending_facility     : Optional[str] = None,
        receiving_application: str  = "ICU_GUARD",
        receiving_facility   : str  = "HOSPITAL_CAIRO",
        panel_id             : str  = "TELEMETRY_PANEL",
        patient_family_name  : str  = "PATIENT",
        patient_given_name   : str  = "ICU",
        patient_dob          : str  = "19500101",
        patient_gender       : str  = "U",
        timestamp            : Optional[datetime] = None,
    ):
        self._patient_id            = patient_id
        self._bed_id                = bed_id
        self._sending_application   = sending_application
        self._sending_facility      = sending_facility or bed_id
        self._receiving_application = receiving_application
        self._receiving_facility    = receiving_facility
        self._panel_id              = panel_id
        self._patient_family_name   = patient_family_name
        self._patient_given_name    = patient_given_name
        self._patient_dob           = patient_dob
        self._patient_gender        = patient_gender
        self._timestamp             = timestamp or datetime.now()
        self._observations          : List[ObservationResult] = []
        self._message_control_id    = self._generate_id()

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_id() -> str:
        """Generate a short unique message control ID."""
        return f"MSG{uuid.uuid4().hex[:8].upper()}"

    # ── Public API ───────────────────────────────────────────────────────────

    def add_observation(
        self,
        loinc_code      : LOINCCode,
        value           : float,
        abnormal_flag   : Optional[str] = None,
        obs_time        : Optional[datetime] = None,
    ) -> "HL7MessageBuilder":
        """
        Add a single observation to the message.

        Args:
            loinc_code    : A LOINCCode instance (e.g. LOINC.HEART_RATE)
            value         : The numeric measurement value
            abnormal_flag : Override auto-calculated flag ('N','L','H','LL','HH')
            obs_time      : Individual observation timestamp (default = message ts)

        Returns:
            self (for method chaining)
        """
        flag_str = abnormal_flag or loinc_code.interpret(value)
        flag     = AbnormalFlag.from_string(flag_str)

        self._observations.append(
            ObservationResult(
                loinc_code      = loinc_code,
                value           = value,
                abnormal_flag   = flag,
                observation_time = obs_time or self._timestamp,
            )
        )
        return self

    def reset(self) -> "HL7MessageBuilder":
        """Clear all observations to reuse the builder for a new message."""
        self._observations.clear()
        self._message_control_id = self._generate_id()
        return self

    def build(self) -> HL7Message:
        """
        Assemble and return the complete HL7Message.

        Raises:
            ValueError: If no observations have been added.
        """
        if not self._observations:
            raise ValueError("Cannot build HL7 message: no observations added.")

        segments: List[str] = []

        # ── MSH ─────────────────────────────────────────────────────────────
        msh = MSH(
            sending_application  = self._sending_application,
            sending_facility     = self._sending_facility,
            receiving_application= self._receiving_application,
            receiving_facility   = self._receiving_facility,
            message_type         = "ORU",
            trigger_event        = "R01",
            message_control_id   = self._message_control_id,
            processing_id        = "P",
            timestamp            = self._timestamp,
        )
        segments.append(msh.build())

        # ── PID ─────────────────────────────────────────────────────────────
        pid = PID(
            set_id       = 1,
            patient_id   = self._patient_id,
            id_namespace = "EICU",
            family_name  = self._patient_family_name,
            given_name   = self._patient_given_name,
            date_of_birth= self._patient_dob,
            gender       = self._patient_gender,
        )
        segments.append(pid.build())

        # ── OBR ─────────────────────────────────────────────────────────────
        obr = OBR(
            set_id           = 1,
            panel_id         = self._panel_id,
            observation_time = self._timestamp,
        )
        segments.append(obr.build())

        # ── OBX (one per observation) ────────────────────────────────────────
        for idx, obs in enumerate(self._observations, start=1):
            ref_range = ""
            if (obs.loinc_code.normal_low is not None and
                    obs.loinc_code.normal_high is not None):
                ref_range = (
                    f"{obs.loinc_code.normal_low}"
                    f"-{obs.loinc_code.normal_high}"
                )

            obx = OBX(
                set_id            = idx,
                value_type        = "NM",
                observation_id    = obs.loinc_code.as_hl7_identifier(),
                value             = f"{obs.value:.4g}",
                unit              = obs.loinc_code.unit,
                reference_range   = ref_range,
                abnormal_flag     = obs.abnormal_flag.value,
                observation_status= "F",
                observation_time  = obs.observation_time,
            )
            segments.append(obx.build())

        return HL7Message(
            message_id   = self._message_control_id,
            segments     = segments,
            observations = list(self._observations),
        )

    # ── Convenience factory methods ──────────────────────────────────────────

    @classmethod
    def monitor_message(
        cls,
        patient_id  : str,
        bed_id      : str,
        heart_rate  : float,
        sbp         : float,
        dbp         : float,
        map_bp      : float,
        resp_rate   : float,
        spo2        : float,
        temperature : float,
        timestamp   : Optional[datetime] = None,
    ) -> HL7Message:
        """Build a complete Patient Monitor ORU^R01 message."""
        builder = cls(
            patient_id           = patient_id,
            bed_id               = bed_id,
            sending_application  = "PHILIPS_INTELLIVUE",
            sending_facility     = bed_id,
            panel_id             = "TELEMETRY_PANEL",
            timestamp            = timestamp,
        )
        return (
            builder
            .add_observation(LOINC.HEART_RATE,   heart_rate)
            .add_observation(LOINC.SYSTOLIC_BP,  sbp)
            .add_observation(LOINC.DIASTOLIC_BP, dbp)
            .add_observation(LOINC.MEAN_BP,      map_bp)
            .add_observation(LOINC.RESP_RATE,    resp_rate)
            .add_observation(LOINC.OXYGEN_SAT,   spo2)
            .add_observation(LOINC.TEMPERATURE,  temperature)
            .build()
        )

    @classmethod
    def abg_message(
        cls,
        patient_id : str,
        bed_id     : str,
        ph         : float,
        pao2       : float,
        paco2      : float,
        lactate    : float,
        timestamp  : Optional[datetime] = None,
    ) -> HL7Message:
        """Build a complete ABG Analyzer ORU^R01 message."""
        builder = cls(
            patient_id           = patient_id,
            bed_id               = bed_id,
            sending_application  = "RADIOMETER_ABL800",
            sending_facility     = bed_id,
            panel_id             = "ABG_PANEL",
            timestamp            = timestamp,
        )
        return (
            builder
            .add_observation(LOINC.PH,      ph)
            .add_observation(LOINC.PAO2,    pao2)
            .add_observation(LOINC.PACO2,   paco2)
            .add_observation(LOINC.LACTATE, lactate)
            .build()
        )
