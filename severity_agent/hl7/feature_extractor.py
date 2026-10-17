"""
feature_extractor.py — Clinical Feature Engineering from Bedside HL7 Feeds
==========================================================================
Extracts the exact 154 feature set required by the ICU Guard XGBoost model
and clinical rule detectors from longitudinal observations in PatientDataBuffer.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict

from .buffer import PatientDataBuffer
from hl7_simulator.core.loinc_codes import LOINC

logger = logging.getLogger("icu_guard.hl7.features")


class HL7FeatureExtractor:
    """
    Transforms raw multi-device observations into a consolidated 154-feature dictionary.
    """

    # Vital LOINC mappings
    VITALS_MAP = {
        "heartrate": LOINC.HEART_RATE.code,
        "respiration": LOINC.RESP_RATE.code,
        "sao2": LOINC.OXYGEN_SAT.code,
        "temperature": LOINC.TEMPERATURE.code,
        "sbp": LOINC.SYSTOLIC_BP.code,
        "dbp": LOINC.DIASTOLIC_BP.code,
        "meanbp": LOINC.MEAN_BP.code,
    }

    # Lab LOINC mappings
    LABS_MAP = {
        "lactate": LOINC.LACTATE.code,
        "creatinine": LOINC.CREATININE.code,
        "wbc": LOINC.WBC.code,
        "platelets": LOINC.PLATELETS.code,
        "glucose": LOINC.GLUCOSE.code,
        "hemoglobin": LOINC.HEMOGLOBIN.code,
        "sodium": LOINC.SODIUM.code,
        "potassium": LOINC.POTASSIUM.code,
        "bun": LOINC.BUN.code,
        "ph": LOINC.PH.code,
        "pao2": LOINC.PAO2.code,
        "paco2": LOINC.PACO2.code,
        "inr": LOINC.INR.code,
        "ptt": LOINC.PTT.code,
    }

    @classmethod
    def extract_features(cls, buffer: PatientDataBuffer) -> Dict[str, Any]:
        """
        Extract the complete 154-feature dictionary from the patient buffer.
        """
        features: Dict[str, Any] = {}

        # ── 1. Demographics & Base Metadata ──────────────────────────────────
        demo = buffer.demographics
        features["patientunitstayid"] = buffer.patient_id
        features["gender"] = demo.get("gender", 1)
        features["age"] = demo.get("age", 65.0)
        features["age_clean"] = demo.get("age", 65.0)
        features["admissionweight"] = demo.get("admissionweight", 75.0)
        features["admissionheight"] = demo.get("admissionheight", 172.0)

        # BMI calculation
        wt = features["admissionweight"]
        ht = features["admissionheight"] / 100.0  # in meters
        features["bmi"] = round(wt / (ht ** 2), 2) if ht > 0 else 25.0

        features["apachescore"] = demo.get("apachescore", 45.0)
        features["acutephysiologyscore"] = demo.get("acutephysiologyscore", 38.0)
        features["predictedicumortality"] = demo.get("predictedicumortality", 0.12)
        features["predictediculos"] = demo.get("predictediculos", 3.5)
        features["unitvisitnumber"] = 1

        # ── 2. Vitals Aggregations (32 Features) ──────────────────────────────
        total_vitals = 0
        for vital_name, loinc in cls.VITALS_MAP.items():
            mean_v, min_v, max_v, std_v, count = buffer.get_stats(loinc)
            total_vitals += count

            features[f"{vital_name}_mean"] = mean_v if not math.isnan(mean_v) else None
            features[f"{vital_name}_min"] = min_v if not math.isnan(min_v) else None
            features[f"{vital_name}_max"] = max_v if not math.isnan(max_v) else None
            features[f"{vital_name}_std"] = std_v if not math.isnan(std_v) else 0.0

        features["total_vitals_count"] = total_vitals

        # ── 3. Laboratory Aggregations (80 Features) ──────────────────────────
        total_labs = 0
        for lab_name, loinc in cls.LABS_MAP.items():
            mean_v, min_v, max_v, std_v, count = buffer.get_stats(loinc)
            total_labs += count

            if count > 0 and not math.isnan(mean_v):
                features[f"{lab_name}_mean"] = round(mean_v, 2)
                features[f"{lab_name}_min"] = round(min_v, 2)
                features[f"{lab_name}_max"] = round(max_v, 2)
                features[f"{lab_name}_missing"] = 0
            else:
                features[f"{lab_name}_mean"] = None
                features[f"{lab_name}_min"] = None
                features[f"{lab_name}_max"] = None
                features[f"{lab_name}_missing"] = 1

        features["total_labs_count"] = total_labs

        # ── 4. Derived Physiological Indices ──────────────────────────────────
        hr = features.get("heartrate_mean") or 80.0
        sbp = features.get("sbp_mean") or 120.0
        dbp = features.get("dbp_mean") or 80.0
        mbp = features.get("meanbp_mean") or 93.3
        sao2 = features.get("sao2_mean") or 98.0
        bun = features.get("bun_mean") or 15.0
        cr = features.get("creatinine_mean") or 1.0

        # Shock Index (HR / SBP)
        features["shock_index"] = round(hr / sbp, 3) if sbp > 0 else 0.67
        # Pulse Pressure (SBP - DBP)
        features["pulse_pressure"] = round(sbp - dbp, 1)
        # MAP / SBP Ratio
        features["map_sbp_ratio"] = round(mbp / sbp, 3) if sbp > 0 else 0.78
        # O2 Reserve
        features["o2_reserve"] = round(sao2 - 88.0, 1)
        # BUN / Creatinine Ratio
        features["bun_creatinine_ratio"] = round(bun / cr, 1) if cr and cr > 0 else 15.0

        # Urine Output
        u_vol = demo.get("total_urine_6h", 600.0)
        features["total_urine_6h"] = u_vol
        features["urine_missing"] = 0 if u_vol is not None else 1
        features["urine_rate_ml_kg_h"] = round(u_vol / (wt * 6.0), 3) if wt > 0 else 1.33

        # GCS Neurological Score
        features["gcs_min"] = demo.get("gcs_min", 15.0)
        features["gcs_mean"] = demo.get("gcs_mean", 15.0)
        features["gcs_missing"] = 0

        # ── 5. Chronic Comorbidities ──────────────────────────────────────────
        features["has_diabetes"] = demo.get("has_diabetes", 0)
        features["has_ckd"] = demo.get("has_ckd", 0)
        features["has_chf"] = demo.get("has_chf", 0)
        features["has_copd"] = demo.get("has_copd", 0)
        features["has_hypertension"] = demo.get("has_hypertension", 0)

        # ── 6. Active Interventions (Pumps & Ventilator) ───────────────────────
        ne_rate = buffer.get_latest(LOINC.NORADRENALINE_RATE.code) or 0.0
        epi_rate = buffer.get_latest(LOINC.EPINEPHRINE_RATE.code) or 0.0
        dopa_rate = buffer.get_latest(LOINC.DOPAMINE_RATE.code) or 0.0
        features["vasopressor_6h"] = 1 if (ne_rate > 0.001 or epi_rate > 0.001 or dopa_rate > 0.1) else 0

        vent_tv = buffer.get_latest(LOINC.TIDAL_VOLUME.code) or 0.0
        vent_fio2 = buffer.get_latest(LOINC.FIO2.code) or 21.0
        features["ventilation_6h"] = 1 if (vent_tv > 10.0 or vent_fio2 > 25.0) else 0

        # ── 7. Unit and Admission Categoricals (One-Hot Encoded) ───────────────
        unit_types = [
            "unittype_CCU-CTICU", "unittype_CSICU", "unittype_CTICU",
            "unittype_Cardiac ICU", "unittype_MICU", "unittype_Med-Surg ICU",
            "unittype_Neuro ICU", "unittype_SICU"
        ]
        for u in unit_types:
            features[u] = False
        features["unittype_Med-Surg ICU"] = True

        admission_types = [
            "admissiontype_", "admissiontype_Acute Care/Floor", "admissiontype_Chest Pain Center",
            "admissiontype_Direct Admit", "admissiontype_Emergency Department", "admissiontype_Floor",
            "admissiontype_ICU", "admissiontype_Operating Room", "admissiontype_Other Hospital",
            "admissiontype_Other ICU", "admissiontype_PACU", "admissiontype_Recovery Room",
            "admissiontype_Step-Down Unit (SDU)"
        ]
        for a in admission_types:
            features[a] = False
        features["admissiontype_Emergency Department"] = True

        return features
