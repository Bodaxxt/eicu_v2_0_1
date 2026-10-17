"""
test_hl7_core.py — Unit and Integration Tests for HL7 Core Foundation
======================================================================
Tests:
  1. LOINC code registry & abnormal interpretation
  2. Segment formatting (MSH, PID, OBR, OBX, ACK)
  3. HL7MessageBuilder fluent API & MLLP framing
  4. MLLP Server & Client TCP integration (send & ACK receipt)
  5. Vital signs simulation scenario
"""

import asyncio
import unittest
from datetime import datetime

from hl7_simulator.core import (
    LOINC,
    LOINCCode,
    MSH,
    PID,
    OBR,
    OBX,
    AbnormalFlag,
    HL7MessageBuilder,
    MLLPServer,
    MLLPClient,
)
from hl7_simulator.core.message_builder import MLLP_START, MLLP_END, MLLP_CR
from hl7_simulator.scenarios.vital_signs import VitalSignsScenario


class TestLOINCCodes(unittest.TestCase):
    """Test the LOINC code registry and reference range evaluations."""

    def test_required_codes_present(self):
        expected_codes = {
            "8867-4": "HEART_RATE",
            "8478-0": "MEAN_BP",
            "9279-1": "RESP_RATE",
            "2708-6": "OXYGEN_SAT",
            "8310-5": "TEMPERATURE",
            "8480-6": "SYSTOLIC_BP",
            "8462-4": "DIASTOLIC_BP",
            "2744-1": "ARTERIAL_PH",
            "2703-7": "PAO2",
            "2019-8": "PACO2",
            "2524-7": "LACTATE",
            "2160-0": "CREATININE",
            "3094-0": "BUN",
            "6690-2": "WBC",
            "777-3": "PLATELETS",
            "718-7": "HEMOGLOBIN",
            "2345-7": "GLUCOSE",
            "2951-2": "SODIUM",
            "2823-3": "POTASSIUM",
            "6301-6": "INR",
            "14979-9": "PTT",
        }
        for code_str, expected_name in expected_codes.items():
            found = LOINC.by_code(code_str)
            self.assertIsNotNone(found, f"LOINC code {code_str} not found in registry")
            self.assertEqual(found.display_name, expected_name)

    def test_interpret_normal_and_abnormal(self):
        hr = LOINC.HEART_RATE  # Normal 60 - 100
        self.assertEqual(hr.interpret(75), "N")
        self.assertEqual(hr.interpret(105), "H")
        self.assertEqual(hr.interpret(135), "HH")
        self.assertEqual(hr.interpret(55), "L")
        self.assertEqual(hr.interpret(40), "LL")

    def test_as_hl7_identifier(self):
        hr = LOINC.HEART_RATE
        self.assertEqual(hr.as_hl7_identifier(), "8867-4^HEART_RATE^LN")


class TestSegments(unittest.TestCase):
    """Test individual HL7 segment construction."""

    def test_msh_formatting(self):
        ts = datetime(2026, 10, 16, 1, 0, 0)
        msh = MSH(
            sending_application="PHILIPS_INTELLIVUE",
            sending_facility="ICU_BED_04",
            receiving_application="ICU_GUARD",
            receiving_facility="HOSPITAL_CAIRO",
            message_type="ORU",
            trigger_event="R01",
            message_control_id="MSG00104",
            processing_id="P",
            timestamp=ts,
        )
        expected = "MSH|^~\\&|PHILIPS_INTELLIVUE|ICU_BED_04|ICU_GUARD|HOSPITAL_CAIRO|20261016010000||ORU^R01|MSG00104|P|2.5"
        self.assertEqual(msh.build(), expected)

    def test_pid_formatting(self):
        pid = PID(
            set_id=1,
            patient_id="224606",
            id_namespace="EICU",
            family_name="DOE",
            given_name="PATIENT",
            date_of_birth="19500101",
            gender="M",
        )
        expected = "PID|1||224606^^^EICU||DOE^PATIENT||19500101|M"
        self.assertEqual(pid.build(), expected)

    def test_obr_formatting(self):
        ts = datetime(2026, 10, 16, 1, 0, 0)
        obr = OBR(set_id=1, panel_id="TELEMETRY_PANEL", observation_time=ts)
        expected = "OBR|1|||TELEMETRY_PANEL|||20261016010000"
        self.assertEqual(obr.build(), expected)

    def test_obx_formatting(self):
        obx = OBX(
            set_id=1,
            value_type="NM",
            observation_id="8867-4^HEART_RATE^LN",
            value="112",
            unit="bpm",
            reference_range="60-100",
            abnormal_flag="H",
            observation_status="F",
        )
        res = obx.build()
        self.assertTrue(res.startswith("OBX|1|NM|8867-4^HEART_RATE^LN||112|bpm|60-100|H||F|"))


class TestHL7MessageBuilder(unittest.TestCase):
    """Test high-level message building and MLLP framing."""

    def test_fluent_builder(self):
        msg = (
            HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04")
            .add_observation(LOINC.HEART_RATE, 112.0)
            .add_observation(LOINC.MEAN_BP, 46.0)
            .build()
        )
        raw = msg.to_string()
        self.assertIn("MSH|^~\\&|", raw)
        self.assertIn("PID|1||224606^^^EICU|", raw)
        self.assertIn("OBR|1|||TELEMETRY_PANEL|", raw)
        self.assertIn("OBX|1|NM|8867-4^HEART_RATE^LN||112|bpm|", raw)
        self.assertIn("OBX|2|NM|8478-0^MEAN_BP^LN||46|mmHg|", raw)

    def test_mllp_framing(self):
        msg = (
            HL7MessageBuilder(patient_id="224606")
            .add_observation(LOINC.HEART_RATE, 80.0)
            .build()
        )
        mllp_bytes = msg.to_mllp()
        self.assertEqual(mllp_bytes[0:1], b"\x0b")
        self.assertEqual(mllp_bytes[-2:], b"\x1c\r")

    def test_factory_monitor_message(self):
        msg = HL7MessageBuilder.monitor_message(
            patient_id="224606",
            bed_id="ICU_BED_04",
            heart_rate=112.0,
            sbp=90.0,
            dbp=50.0,
            map_bp=46.0,
            resp_rate=18.0,
            spo2=84.0,
            temperature=37.5,
        )
        raw = msg.to_string()
        self.assertIn("PHILIPS_INTELLIVUE", raw)
        self.assertEqual(len(msg.observations), 7)


class TestMLLPServerIntegration(unittest.TestCase):
    """Test TCP MLLP transmission and acknowledgement."""

    def test_send_and_receive_ack(self):
        async def _test():
            server_port = 6699  # Isolated port for test
            received_messages = []

            def handle_msg(raw):
                received_messages.append(raw)
                return None  # Let default ACK logic build the response

            server = MLLPServer(host="127.0.0.1", port=server_port, on_message=handle_msg)
            await server.start()

            try:
                client = MLLPClient(host="127.0.0.1", port=server_port, timeout=2.0)
                sample_msg = (
                    HL7MessageBuilder(patient_id="224606", bed_id="ICU_BED_04")
                    .add_observation(LOINC.HEART_RATE, 112.0)
                    .build()
                )

                ack = await client.send_message(sample_msg.to_string())

                # Validate server received message
                self.assertEqual(len(received_messages), 1)
                self.assertIn("8867-4^HEART_RATE^LN", received_messages[0])

                # Validate ACK response
                self.assertIn("MSA|AA|" + sample_msg.message_id, ack)
            finally:
                await server.stop()

        asyncio.run(_test())

    def test_vital_signs_scenario(self):
        scenario = VitalSignsScenario(patient_id="224606", bed_id="ICU_BED_04")
        messages = list(scenario.generate_messages())
        self.assertEqual(len(messages), 4)
        # Check first frame (stable)
        self.assertIn("78", messages[0].to_string())
        # Check last frame (severe septic shock)
        self.assertIn("118", messages[3].to_string())
        self.assertIn("46", messages[3].to_string())


if __name__ == "__main__":
    unittest.main()
