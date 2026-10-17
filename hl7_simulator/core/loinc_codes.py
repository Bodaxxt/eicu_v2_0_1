"""
loinc_codes.py — LOINC Code Library for ICU Guard HL7 Simulator
================================================================
Covers all 21 features used in the ML model training dataset,
mapped to their official LOINC identifiers and physical units.

Reference: https://loinc.org/
Protocol:  HL7 v2.5 — OBX-3 (Observation Identifier)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LOINCCode:
    """
    Represents a single LOINC code entry.

    Attributes:
        code        : LOINC numeric code (e.g. '8867-4')
        display_name: Human-readable observation name
        unit        : Default unit of measure (UCUM)
        normal_low  : Lower bound of normal range (optional)
        normal_high : Upper bound of normal range (optional)
        device      : Source device category
        hl7_field   : Typical HL7 segment field this maps to
    """
    code         : str
    display_name : str
    unit         : str
    normal_low   : Optional[float]
    normal_high  : Optional[float]
    device       : str   # "monitor" | "abg" | "lab" | "nursing" | "pump" | "ventilator"
    hl7_field    : str = "OBX-3"

    def as_hl7_identifier(self) -> str:
        """Return OBX-3 formatted string: code^display^LN"""
        return f"{self.code}^{self.display_name}^LN"

    def interpret(self, value: float) -> str:
        """
        Return HL7 abnormal flag for a given value.
        Returns: 'LL' | 'L' | 'N' | 'H' | 'HH' | 'U' (unknown / no range)
        """
        if self.normal_low is None or self.normal_high is None:
            return "U"
        span = self.normal_high - self.normal_low
        critical_margin = span * 0.20  # 20% outside normal = critical

        if value < self.normal_low - critical_margin:
            return "LL"
        elif value < self.normal_low:
            return "L"
        elif value > self.normal_high + critical_margin:
            return "HH"
        elif value > self.normal_high:
            return "H"
        else:
            return "N"


# ─────────────────────────────────────────────────────────────────────────────
# LOINC Registry — all 21 ML features + extras
# ─────────────────────────────────────────────────────────────────────────────

class LOINC:
    """
    Static registry of LOINC codes used by ICU Guard.

    Usage:
        code = LOINC.HEART_RATE
        flag = code.interpret(45)          # → 'LL'
        hl7  = code.as_hl7_identifier()    # → '8867-4^HEART_RATE^LN'
    """

    # ── Patient Monitor (Philips IntelliVue / Mindray / GE CARESCAPE) ─────────
    HEART_RATE = LOINCCode(
        code="8867-4",
        display_name="HEART_RATE",
        unit="bpm",
        normal_low=60.0,
        normal_high=100.0,
        device="monitor",
    )
    SYSTOLIC_BP = LOINCCode(
        code="8480-6",
        display_name="SYSTOLIC_BP",
        unit="mmHg",
        normal_low=90.0,
        normal_high=140.0,
        device="monitor",
    )
    DIASTOLIC_BP = LOINCCode(
        code="8462-4",
        display_name="DIASTOLIC_BP",
        unit="mmHg",
        normal_low=60.0,
        normal_high=90.0,
        device="monitor",
    )
    MEAN_BP = LOINCCode(
        code="8478-0",
        display_name="MEAN_BP",
        unit="mmHg",
        normal_low=65.0,
        normal_high=110.0,
        device="monitor",
    )
    RESP_RATE = LOINCCode(
        code="9279-1",
        display_name="RESP_RATE",
        unit="breaths/min",
        normal_low=12.0,
        normal_high=20.0,
        device="monitor",
    )
    OXYGEN_SAT = LOINCCode(
        code="2708-6",
        display_name="OXYGEN_SAT",
        unit="%",
        normal_low=95.0,
        normal_high=100.0,
        device="monitor",
    )
    TEMPERATURE = LOINCCode(
        code="8310-5",
        display_name="TEMPERATURE",
        unit="Cel",
        normal_low=36.5,
        normal_high=37.5,
        device="monitor",
    )

    # ── ABG Analyzer (Radiometer ABL800 / Roche Cobas b 123) ─────────────────
    PH = LOINCCode(
        code="2744-1",
        display_name="ARTERIAL_PH",
        unit="[pH]",
        normal_low=7.35,
        normal_high=7.45,
        device="abg",
    )
    PAO2 = LOINCCode(
        code="2703-7",
        display_name="PAO2",
        unit="mmHg",
        normal_low=80.0,
        normal_high=100.0,
        device="abg",
    )
    PACO2 = LOINCCode(
        code="2019-8",
        display_name="PACO2",
        unit="mmHg",
        normal_low=35.0,
        normal_high=45.0,
        device="abg",
    )
    LACTATE = LOINCCode(
        code="2524-7",
        display_name="LACTATE",
        unit="mmol/L",
        normal_low=0.5,
        normal_high=2.0,
        device="abg",
    )

    # ── Central Laboratory LIS (Roche / Abbott / Siemens) ────────────────────
    CREATININE = LOINCCode(
        code="2160-0",
        display_name="CREATININE",
        unit="mg/dL",
        normal_low=0.6,
        normal_high=1.2,
        device="lab",
    )
    BUN = LOINCCode(
        code="3094-0",
        display_name="BUN",
        unit="mg/dL",
        normal_low=7.0,
        normal_high=20.0,
        device="lab",
    )
    WBC = LOINCCode(
        code="6690-2",
        display_name="WBC",
        unit="10*3/uL",
        normal_low=4.0,
        normal_high=11.0,
        device="lab",
    )
    PLATELETS = LOINCCode(
        code="777-3",
        display_name="PLATELETS",
        unit="10*3/uL",
        normal_low=150.0,
        normal_high=400.0,
        device="lab",
    )
    HEMOGLOBIN = LOINCCode(
        code="718-7",
        display_name="HEMOGLOBIN",
        unit="g/dL",
        normal_low=12.0,
        normal_high=17.5,
        device="lab",
    )
    GLUCOSE = LOINCCode(
        code="2345-7",
        display_name="GLUCOSE",
        unit="mg/dL",
        normal_low=70.0,
        normal_high=110.0,
        device="lab",
    )
    SODIUM = LOINCCode(
        code="2951-2",
        display_name="SODIUM",
        unit="mmol/L",
        normal_low=136.0,
        normal_high=145.0,
        device="lab",
    )
    POTASSIUM = LOINCCode(
        code="2823-3",
        display_name="POTASSIUM",
        unit="mmol/L",
        normal_low=3.5,
        normal_high=5.0,
        device="lab",
    )
    INR = LOINCCode(
        code="6301-6",
        display_name="INR",
        unit="{INR}",
        normal_low=0.8,
        normal_high=1.2,
        device="lab",
    )
    PTT = LOINCCode(
        code="14979-9",
        display_name="PTT",
        unit="s",
        normal_low=25.0,
        normal_high=35.0,
        device="lab",
    )

    # ── Nursing / EMR ─────────────────────────────────────────────────────────
    GCS = LOINCCode(
        code="9269-2",
        display_name="GCS_TOTAL",
        unit="{score}",
        normal_low=13.0,
        normal_high=15.0,
        device="nursing",
    )
    URINE_OUTPUT = LOINCCode(
        code="9192-6",
        display_name="URINE_OUTPUT_6H",
        unit="mL",
        normal_low=180.0,    # ~0.5 ml/kg/h × 60kg × 6h
        normal_high=2400.0,
        device="nursing",
    )

    # ── Smart Pump / Ventilator ───────────────────────────────────────────────
    TIDAL_VOLUME = LOINCCode(
        code="76222-9",
        display_name="TIDAL_VOLUME",
        unit="mL",
        normal_low=350.0,
        normal_high=550.0,
        device="ventilator",
    )
    PEEP = LOINCCode(
        code="76248-4",
        display_name="PEEP",
        unit="cm[H2O]",
        normal_low=5.0,
        normal_high=10.0,
        device="ventilator",
    )
    FIO2 = LOINCCode(
        code="3150-0",
        display_name="FIO2",
        unit="%",
        normal_low=21.0,
        normal_high=60.0,
        device="ventilator",
    )
    PEAK_PRESSURE = LOINCCode(
        code="76251-8",
        display_name="PEAK_PRESSURE",
        unit="cm[H2O]",
        normal_low=15.0,
        normal_high=35.0,
        device="ventilator",
    )
    VENTILATOR_MODE = LOINCCode(
        code="76228-6",
        display_name="VENTILATOR_MODE",
        unit="",
        normal_low=None,
        normal_high=None,
        device="ventilator",
    )
    NORADRENALINE_RATE = LOINCCode(
        code="77137-8",
        display_name="NORADRENALINE_RATE",
        unit="ug/kg/min",
        normal_low=0.0,
        normal_high=0.1,
        device="pump",
    )
    EPINEPHRINE_RATE = LOINCCode(
        code="2272-6",
        display_name="EPINEPHRINE_RATE",
        unit="ug/kg/min",
        normal_low=0.0,
        normal_high=0.05,
        device="pump",
    )
    DOPAMINE_RATE = LOINCCode(
        code="2215-5",
        display_name="DOPAMINE_RATE",
        unit="ug/kg/min",
        normal_low=0.0,
        normal_high=5.0,
        device="pump",
    )
    PROPOFOL_RATE = LOINCCode(
        code="11451-2",
        display_name="PROPOFOL_RATE",
        unit="ug/kg/min",
        normal_low=10.0,
        normal_high=50.0,
        device="pump",
    )
    FENTANYL_RATE = LOINCCode(
        code="11450-4",
        display_name="FENTANYL_RATE",
        unit="ug/h",
        normal_low=25.0,
        normal_high=100.0,
        device="pump",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Lookup helpers
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def by_code(cls, code: str) -> Optional[LOINCCode]:
        """Return LOINCCode by LOINC number string (e.g. '8867-4')."""
        for attr in dir(cls):
            val = getattr(cls, attr)
            if isinstance(val, LOINCCode) and val.code == code:
                return val
        return None

    @classmethod
    def by_device(cls, device: str) -> list[LOINCCode]:
        """Return all LOINCCodes for a given device category."""
        result = []
        for attr in dir(cls):
            val = getattr(cls, attr)
            if isinstance(val, LOINCCode) and val.device == device:
                result.append(val)
        return result

    @classmethod
    def all_codes(cls) -> list[LOINCCode]:
        """Return every registered LOINCCode."""
        return [
            getattr(cls, a)
            for a in dir(cls)
            if isinstance(getattr(cls, a), LOINCCode)
        ]
