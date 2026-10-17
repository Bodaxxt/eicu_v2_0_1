"""
segments.py — HL7 v2.5 Segment Builders
=========================================
Builds individual HL7 segments as formatted strings.

Segment order in ORU^R01:
    MSH → PID → OBR → OBX (×N)

Field separator  : |
Component sep    : ^
Repetition sep   : ~
Escape char      : \\
Subcomponent sep : &

Reference: HL7 v2.5 Chapter 7 (Observation Reporting)
"""

from __future__ import annotations
from datetime  import datetime
from enum      import Enum
from typing    import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

FIELD_SEP     = "|"
COMPONENT_SEP = "^"
ENCODING_CHARS = "^~\\&"
HL7_VERSION   = "2.5"


def _ts(dt: Optional[datetime] = None) -> str:
    """Format datetime as HL7 timestamp: YYYYMMDDHHmmss"""
    return (dt or datetime.now()).strftime("%Y%m%d%H%M%S")


# ─────────────────────────────────────────────────────────────────────────────
# Abnormal Flag Enum (OBX-8)
# ─────────────────────────────────────────────────────────────────────────────

class AbnormalFlag(str, Enum):
    CRITICALLY_LOW   = "LL"  # Critical low   (panic value)
    LOW              = "L"   # Below normal
    NORMAL           = "N"   # Within normal range
    HIGH             = "H"   # Above normal
    CRITICALLY_HIGH  = "HH"  # Critical high  (panic value)
    UNKNOWN          = "U"   # No reference range

    @classmethod
    def from_string(cls, s: str) -> "AbnormalFlag":
        mapping = {
            "LL": cls.CRITICALLY_LOW,
            "L":  cls.LOW,
            "N":  cls.NORMAL,
            "H":  cls.HIGH,
            "HH": cls.CRITICALLY_HIGH,
        }
        return mapping.get(s, cls.UNKNOWN)


# ─────────────────────────────────────────────────────────────────────────────
# MSH — Message Header Segment
# ─────────────────────────────────────────────────────────────────────────────

class MSH:
    """
    MSH — Message Header

    Example:
        MSH|^~\\&|PHILIPS_INTELLIVUE|ICU_BED_04|ICU_GUARD|HOSPITAL_CAIRO|
        20261016010000||ORU^R01|MSG00104|P|2.5
    """

    def __init__(
        self,
        sending_application : str  = "PHILIPS_INTELLIVUE",
        sending_facility    : str  = "ICU_BED_04",
        receiving_application: str = "ICU_GUARD",
        receiving_facility  : str  = "HOSPITAL_CAIRO",
        message_type        : str  = "ORU",
        trigger_event       : str  = "R01",
        message_control_id  : str  = "MSG00001",
        processing_id       : str  = "P",       # P=Production, T=Test
        timestamp           : Optional[datetime] = None,
    ):
        self.sending_application  = sending_application
        self.sending_facility     = sending_facility
        self.receiving_application = receiving_application
        self.receiving_facility   = receiving_facility
        self.message_type         = message_type
        self.trigger_event        = trigger_event
        self.message_control_id   = message_control_id
        self.processing_id        = processing_id
        self.timestamp            = timestamp or datetime.now()

    def build(self) -> str:
        """Return the formatted MSH segment string."""
        fields = [
            "MSH",
            ENCODING_CHARS,                             # MSH-2
            self.sending_application,                   # MSH-3
            self.sending_facility,                      # MSH-4
            self.receiving_application,                 # MSH-5
            self.receiving_facility,                    # MSH-6
            _ts(self.timestamp),                        # MSH-7
            "",                                         # MSH-8 (Security — empty)
            f"{self.message_type}{COMPONENT_SEP}{self.trigger_event}",  # MSH-9
            self.message_control_id,                    # MSH-10
            self.processing_id,                         # MSH-11
            HL7_VERSION,                                # MSH-12
        ]
        return FIELD_SEP.join(fields)


# ─────────────────────────────────────────────────────────────────────────────
# PID — Patient Identification Segment
# ─────────────────────────────────────────────────────────────────────────────

class PID:
    """
    PID — Patient Identification

    Example:
        PID|1||224606^^^EICU||DOE^PATIENT||19500101|M
    """

    def __init__(
        self,
        set_id           : int  = 1,
        patient_id       : str  = "224606",
        id_namespace     : str  = "EICU",
        family_name      : str  = "DOE",
        given_name       : str  = "PATIENT",
        date_of_birth    : str  = "19500101",   # YYYYMMDD
        gender           : str  = "M",           # M | F | U
    ):
        self.set_id        = set_id
        self.patient_id    = patient_id
        self.id_namespace  = id_namespace
        self.family_name   = family_name
        self.given_name    = given_name
        self.date_of_birth = date_of_birth
        self.gender        = gender

    def build(self) -> str:
        cx_id = f"{self.patient_id}^^^{self.id_namespace}"          # PID-3 (CX)
        xpn   = f"{self.family_name}{COMPONENT_SEP}{self.given_name}"  # PID-5 (XPN)

        fields = [
            "PID",
            str(self.set_id),   # PID-1
            "",                 # PID-2 (deprecated patient ID)
            cx_id,              # PID-3
            "",                 # PID-4 (alternate ID — empty)
            xpn,                # PID-5
            "",                 # PID-6 (mother's maiden — empty)
            self.date_of_birth, # PID-7
            self.gender,        # PID-8
        ]
        return FIELD_SEP.join(fields)


# ─────────────────────────────────────────────────────────────────────────────
# OBR — Observation Request Segment
# ─────────────────────────────────────────────────────────────────────────────

class OBR:
    """
    OBR — Observation Request

    Example:
        OBR|1|||TELEMETRY_PANEL|||20261016010000
    """

    PANELS = {
        "monitor"    : "TELEMETRY_PANEL",
        "abg"        : "ABG_PANEL",
        "lab"        : "CHEM_PANEL",
        "nursing"    : "NURSING_ASSESSMENT",
        "ventilator" : "VENTILATOR_PARAMS",
        "pump"       : "INFUSION_PARAMS",
    }

    def __init__(
        self,
        set_id          : int  = 1,
        panel_id        : str  = "TELEMETRY_PANEL",
        observation_time: Optional[datetime] = None,
        ordering_provider: str = "",
    ):
        self.set_id           = set_id
        self.panel_id         = panel_id
        self.observation_time = observation_time or datetime.now()
        self.ordering_provider = ordering_provider

    def build(self) -> str:
        fields = [
            "OBR",
            str(self.set_id),           # OBR-1
            "",                         # OBR-2 (Placer Order — empty)
            "",                         # OBR-3 (Filler Order — empty)
            self.panel_id,              # OBR-4 (Universal Service ID)
            "",                         # OBR-5 (Priority — empty)
            "",                         # OBR-6 (Requested Date — empty)
            _ts(self.observation_time), # OBR-7 (Observation Date/Time)
        ]
        return FIELD_SEP.join(fields)


# ─────────────────────────────────────────────────────────────────────────────
# OBX — Observation/Result Segment
# ─────────────────────────────────────────────────────────────────────────────

class OBX:
    """
    OBX — Observation Result

    Example:
        OBX|1|NM|8867-4^HEART_RATE^LN||112|bpm|60-100|H||F
    """

    def __init__(
        self,
        set_id           : int,
        value_type       : str,             # NM=Numeric, ST=String, CWE=Coded
        observation_id   : str,             # LOINC.as_hl7_identifier()
        value            : str,
        unit             : str = "",
        reference_range  : str = "",
        abnormal_flag    : str = "N",
        observation_status: str = "F",      # F=Final, P=Preliminary, C=Corrected
        observation_time : Optional[datetime] = None,
    ):
        self.set_id            = set_id
        self.value_type        = value_type
        self.observation_id    = observation_id
        self.value             = str(value)
        self.unit              = unit
        self.reference_range   = reference_range
        self.abnormal_flag     = abnormal_flag
        self.observation_status = observation_status
        self.observation_time  = observation_time

    def build(self) -> str:
        ts = _ts(self.observation_time) if self.observation_time else ""
        fields = [
            "OBX",
            str(self.set_id),          # OBX-1  Set ID
            self.value_type,           # OBX-2  Value Type
            self.observation_id,       # OBX-3  Observation Identifier
            "",                        # OBX-4  Observation Sub-ID (empty)
            self.value,                # OBX-5  Observation Value
            self.unit,                 # OBX-6  Units
            self.reference_range,      # OBX-7  Reference Range
            self.abnormal_flag,        # OBX-8  Abnormal Flags
            "",                        # OBX-9  Probability (empty)
            self.observation_status,   # OBX-11 Observation Result Status
            ts,                        # OBX-14 Date/Time of the Observation
        ]
        return FIELD_SEP.join(fields)


# ─────────────────────────────────────────────────────────────────────────────
# ACK — Acknowledgement Segment
# ─────────────────────────────────────────────────────────────────────────────

class ACK:
    """
    ACK — General Acknowledgement

    Sent by ICU Guard after receiving any HL7 message.
    Example:
        MSH|^~\\&|ICU_GUARD|HOSPITAL_CAIRO|PHILIPS_INTELLIVUE|ICU_BED_04|...
        MSA|AA|MSG00104
    """

    def __init__(
        self,
        original_msg_id: str,
        ack_code       : str = "AA",  # AA=Accept, AE=Error, AR=Reject
        receiving_app  : str = "PHILIPS_INTELLIVUE",
        receiving_fac  : str = "ICU_BED_04",
    ):
        self.original_msg_id = original_msg_id
        self.ack_code        = ack_code
        self.receiving_app   = receiving_app
        self.receiving_fac   = receiving_fac

    def build_msh(self) -> str:
        return MSH(
            sending_application  = "ICU_GUARD",
            sending_facility     = "HOSPITAL_CAIRO",
            receiving_application = self.receiving_app,
            receiving_facility   = self.receiving_fac,
            message_type         = "ACK",
            trigger_event        = "R01",
            message_control_id   = f"ACK_{self.original_msg_id}",
        ).build()

    def build_msa(self) -> str:
        return FIELD_SEP.join(["MSA", self.ack_code, self.original_msg_id])

    def build(self) -> str:
        return "\r".join([self.build_msh(), self.build_msa()])
