"""
integration.py — ICU Guard Bridge & Orchestration Layer
========================================================
Connects MLLP Receiver, HL7 Parser, Device Manager, and Feature Extractor
directly to the ICU Guard Severity Agent for end-to-end real-time clinical assessment.

Flow:
    Bedside Devices (HL7 ORU^R01)
      ──> MLLP HL7Receiver
        ──> HL7Parser
          ──> DeviceManager & PatientDataBuffer
            ──> HL7FeatureExtractor (154 Features)
              ──> ICU Guard SeverityAgent
                ──> FullClinicalAssessment (Triage, Differentials, Protocols)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, Dict, Optional, Awaitable

from .receiver import HL7Receiver
from .parser import HL7Parser, ParsedHL7Message
from .device_manager import DeviceManager
from .feature_extractor import HL7FeatureExtractor
from severity_agent.agent import SeverityAgent

logger = logging.getLogger("icu_guard.hl7.bridge")


class ICUGuardBridge:
    """
    End-to-End Orchestrator connecting MLLP telemetry to the Severity Agent.
    """

    DEFAULT_BUNDLE_PATH = "model_artifacts/icu_guard_v4_2_agent_bundle.pkl"

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6661,
        agent: Optional[SeverityAgent] = None,
        bundle_path: Optional[str] = None,
        on_assessment: Optional[Callable[[str, Dict[str, Any]], Optional[Awaitable[None]]]] = None,
    ):
        self.host = host
        self.port = port
        self.on_assessment = on_assessment
        self.device_manager = DeviceManager()

        # Initialize or locate SeverityAgent
        if agent:
            self.agent = agent
        else:
            resolved_bundle = bundle_path or self.DEFAULT_BUNDLE_PATH
            if not os.path.exists(resolved_bundle):
                alt_path = os.path.join(os.path.dirname(__file__), "..", "..", resolved_bundle)
                if os.path.exists(alt_path):
                    resolved_bundle = alt_path

            logger.info(f"[ICUGuardBridge] Initializing SeverityAgent with bundle: {resolved_bundle}")
            self.agent = SeverityAgent(bundle_path=resolved_bundle)

        # MLLP Ingestion Receiver
        self.receiver = HL7Receiver(
            host=self.host,
            port=self.port,
            on_message=self.handle_parsed_message,
        )

        self.last_assessment: Dict[str, Any] = {}
        self.total_assessments_computed = 0

    async def start(self) -> None:
        """Start the live integration bridge."""
        await self.receiver.start()
        logger.info(f"[ICUGuardBridge] Integration bridge active on port {self.port}")

    async def stop(self) -> None:
        """Shutdown the receiver and integration bridge."""
        await self.receiver.stop()
        logger.info("[ICUGuardBridge] Integration bridge stopped.")

    async def handle_parsed_message(self, msg: ParsedHL7Message) -> Dict[str, Any]:
        """
        Callback invoked by HL7Receiver when a valid HL7 message arrives:
        Updates device state, extracts 154 features, and runs severity assessment.
        """
        t0 = time.perf_counter()

        # 1. Update device state and buffer in PatientDataBuffer
        buffer = self.device_manager.process_message(msg)

        # 2. Extract full 154-feature dictionary
        features = HL7FeatureExtractor.extract_features(buffer)

        # 3. Execute ICU Guard Clinical Reasoning
        try:
            assessment = self.agent.full_assessment(
                patient_features=features,
                patient_id=msg.patient_id,
                enable_uncertainty=True,
                enable_recommendations=True,
                enable_trends=True,
                enable_audit=False,  # avoid disk I/O in high-speed streaming
            )
            assessment_dict = assessment.to_dict()
        except Exception as e:
            logger.error(f"[ICUGuardBridge] SeverityAgent assessment error: {e}")
            assessment_dict = {"error": str(e), "patient_id": msg.patient_id}

        self.last_assessment[msg.patient_id] = assessment_dict
        self.total_assessments_computed += 1

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            f"[ICUGuardBridge] Assessed Patient {msg.patient_id} from {msg.device} "
            f"in {elapsed_ms:.1f}ms -> Tier: {assessment_dict.get('severity_tier', 'UNKNOWN')}"
        )

        # 4. Dispatch to external subscriber (e.g. Dashboard / EMR)
        if self.on_assessment:
            try:
                res = self.on_assessment(msg.patient_id, assessment_dict)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"[ICUGuardBridge] Error in on_assessment subscriber: {e}")

        return assessment_dict

    def ingest_raw_sync(self, raw_hl7: str) -> Optional[Dict[str, Any]]:
        """
        Synchronously parse and assess a raw HL7 string (for testing and scripts).
        """
        parsed = HL7Parser.parse(raw_hl7)
        if not parsed:
            return None

        buffer = self.device_manager.process_message(parsed)
        features = HL7FeatureExtractor.extract_features(buffer)
        assessment = self.agent.full_assessment(
            patient_features=features,
            patient_id=parsed.patient_id,
            enable_uncertainty=True,
            enable_recommendations=True,
            enable_trends=True,
            enable_audit=False,
        )
        return assessment.to_dict()
