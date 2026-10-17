"""
test_integration_layer.py — Unit and End-to-End Tests for Integration Layer
=============================================================================
Tests:
  1. HL7Parser segment decomposition and LOINC mapping
  2. PatientDataBuffer window management and rolling statistical aggregations
  3. DeviceManager multi-device inventory tracking and bed assignment
  4. HL7FeatureExtractor 154-feature vector generation
  5. ICUGuardBridge end-to-end ingestion and SeverityAgent assessment execution
  6. Real-time MLLP network transmission with ACK verification
"""

import asyncio
import unittest

from hl7_simulator.core.message_builder import HL7MessageBuilder, LOINC
from hl7_simulator.core.mllp_server import MLLPClient
from severity_agent.hl7.parser import HL7Parser
from severity_agent.hl7.buffer import PatientDataBuffer
from severity_agent.hl7.device_manager import DeviceManager
from severity_agent.hl7.feature_extractor import HL7FeatureExtractor
from severity_agent.hl7.integration import ICUGuardBridge


class TestHL7Parser(unittest.TestCase):
    """Test raw HL7 parsing."""

    def test_parser_with_standard_oru(self):
        msg = (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="PHILIPS_INTELLIVUE")
            .add_observation(LOINC.HEART_RATE, 112.0)
            .add_observation(LOINC.MEAN_BP, 46.0)
            .build()
        )
        parsed = HL7Parser.parse(msg.to_string())

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.device, "PHILIPS_INTELLIVUE")
        self.assertEqual(parsed.bed_id, "ICU_BED_04")
        self.assertEqual(parsed.patient_id, "224606")
        self.assertEqual(len(parsed.observations), 2)
        self.assertEqual(parsed.observations[0].loinc, "8867-4")
        self.assertEqual(parsed.observations[0].value, 112.0)


class TestBufferAndFeatureExtractor(unittest.TestCase):
    """Test buffer statistics and feature extraction."""

    def test_buffer_aggregations(self):
        buffer = PatientDataBuffer(patient_id="224606")
        # Ingest 3 heart rate values: 80, 100, 120 -> mean 100, min 80, max 120
        for val in [80.0, 100.0, 120.0]:
            msg = (
                HL7MessageBuilder(patient_id="224606")
                .add_observation(LOINC.HEART_RATE, val)
                .build()
            )
            parsed = HL7Parser.parse(msg.to_string())
            buffer.add_message(parsed)

        mean_v, min_v, max_v, std_v, count = buffer.get_stats("8867-4")
        self.assertEqual(count, 3)
        self.assertEqual(mean_v, 100.0)
        self.assertEqual(min_v, 80.0)
        self.assertEqual(max_v, 120.0)
        self.assertGreater(std_v, 0.0)

    def test_feature_extractor_154_features(self):
        buffer = PatientDataBuffer(patient_id="224606")
        msg = (
            HL7MessageBuilder(patient_id="224606")
            .add_observation(LOINC.HEART_RATE, 112.0)
            .add_observation(LOINC.SYSTOLIC_BP, 90.0)
            .add_observation(LOINC.DIASTOLIC_BP, 50.0)
            .add_observation(LOINC.MEAN_BP, 63.3)
            .add_observation(LOINC.OXYGEN_SAT, 94.0)
            .add_observation(LOINC.CREATININE, 2.5)
            .add_observation(LOINC.BUN, 45.0)
            .add_observation(LOINC.NORADRENALINE_RATE, 0.25)
            .build()
        )
        parsed = HL7Parser.parse(msg.to_string())
        buffer.add_message(parsed)

        features = HL7FeatureExtractor.extract_features(buffer)

        # Check vital features
        self.assertEqual(features["heartrate_mean"], 112.0)
        self.assertEqual(features["sbp_mean"], 90.0)
        self.assertEqual(features["total_vitals_count"], 5)

        # Check lab features
        self.assertEqual(features["creatinine_mean"], 2.5)
        self.assertEqual(features["creatinine_missing"], 0)

        # Check derived features
        self.assertAlmostEqual(features["shock_index"], 112.0 / 90.0, delta=0.01)
        self.assertEqual(features["pulse_pressure"], 40.0)
        self.assertEqual(features["vasopressor_6h"], 1)


class TestDeviceManager(unittest.TestCase):
    """Test device status tracking."""

    def test_device_registration(self):
        manager = DeviceManager()
        msg = (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="DRAEGER_EVITA")
            .add_observation(LOINC.FIO2, 60.0)
            .build()
        )
        parsed = HL7Parser.parse(msg.to_string())
        manager.process_message(parsed)

        status = manager.get_device_status("DRAEGER_EVITA")
        self.assertIsNotNone(status)
        self.assertEqual(status.device_type, "ventilator")
        self.assertEqual(status.bed_id, "ICU_BED_04")
        self.assertEqual(status.messages_received, 1)


class TestICUGuardBridgeEndToEnd(unittest.TestCase):
    """Test end-to-end integration with SeverityAgent."""

    def test_synchronous_ingest_and_assessment(self):
        bridge = ICUGuardBridge(port=6798)
        # Build multi-parameter septic shock message
        msg = (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="PHILIPS_INTELLIVUE")
            .add_observation(LOINC.HEART_RATE, 128.0)
            .add_observation(LOINC.SYSTOLIC_BP, 74.0)
            .add_observation(LOINC.DIASTOLIC_BP, 35.0)
            .add_observation(LOINC.MEAN_BP, 48.0)
            .add_observation(LOINC.RESP_RATE, 32.0)
            .add_observation(LOINC.OXYGEN_SAT, 85.0)
            .add_observation(LOINC.TEMPERATURE, 39.2)
            .add_observation(LOINC.LACTATE, 6.5)
            .add_observation(LOINC.CREATININE, 2.8)
            .add_observation(LOINC.NORADRENALINE_RATE, 0.45)
            .build()
        )
        assessment = bridge.ingest_raw_sync(msg.to_string())

        self.assertIsNotNone(assessment)
        self.assertIn("severity_tier", assessment)
        tier = assessment["severity_tier"]
        # Patient in severe shock must be categorized as HIGH or CRITICAL
        self.assertIn(tier, ["HIGH", "CRITICAL"])
        self.assertIn("Hemodynamic", assessment.get("organs", {}))

    def test_live_mllp_bridge_and_callback(self):
        async def _test():
            server_port = 6799
            received_assessments = []

            def on_assess(pid, assess):
                received_assessments.append((pid, assess))

            bridge = ICUGuardBridge(port=server_port, on_assessment=on_assess)
            await bridge.start()

            try:
                client = MLLPClient(host="127.0.0.1", port=server_port, timeout=3.0)
                msg = (
                    HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04", sending_application="PHILIPS_INTELLIVUE")
                    .add_observation(LOINC.HEART_RATE, 115.0)
                    .add_observation(LOINC.MEAN_BP, 52.0)
                    .build()
                )
                ack = await client.send_message(msg.to_string())

                # Validate ACK
                self.assertIn("MSA|AA|", ack)
                # Validate assessment computed
                self.assertEqual(len(received_assessments), 1)
                pid, assess = received_assessments[0]
                self.assertEqual(pid, "224606")
                self.assertIn("severity_tier", assess)
            finally:
                await bridge.stop()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
