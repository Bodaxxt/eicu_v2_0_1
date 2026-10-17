"""
test_abg_analyzer.py — Unit, Integration, and Clinical Interpretation Tests for ABG
====================================================================================
Tests:
  1. ABG parameters, LOINC codes, and reference ranges
  2. Clinical Acid-Base Interpretation Engine (4 disorders)
  3. HL7 ORU^R01 generation for ABG_PANEL
  4. 4 Clinical Scenarios (Normal, Metabolic Acidosis, Respiratory Failure, Septic Shock)
  5. MLLP Server integration and ACK receipt
"""

import asyncio
import unittest

from hl7_simulator.core.mllp_server import MLLPServer
from hl7_simulator.devices.abg_analyzer import ABGAnalyzer
from hl7_simulator.scenarios.abg_scenarios import get_abg_scenario


class TestABGInterpretationEngine(unittest.TestCase):
    """Test the clinical acid-base interpretation engine."""

    def test_normal_abg(self):
        readings = {"ph": 7.40, "pao2": 95.0, "paco2": 40.0, "lactate": 1.2}
        interp = ABGAnalyzer.interpret(readings)

        self.assertEqual(interp.ph_status, "Normal pH")
        self.assertEqual(interp.primary_disorder, "Normal Acid-Base Homeostasis")
        self.assertIn("STABLE", interp.verdict)
        self.assertEqual(interp.lactate_status, "Normal Tissue Perfusion")

    def test_metabolic_acidosis(self):
        readings = {"ph": 7.25, "pao2": 80.0, "paco2": 35.0, "lactate": 4.8}
        interp = ABGAnalyzer.interpret(readings)

        self.assertEqual(interp.ph_status, "Acidosis")
        self.assertIn("Metabolic Acidosis", interp.primary_disorder)
        self.assertIn("Severe Hyperlactatemia", interp.lactate_status)
        self.assertIn("CRITICAL - Septic Shock", interp.verdict)

    def test_respiratory_failure(self):
        readings = {"ph": 7.28, "pao2": 60.0, "paco2": 55.0, "lactate": 1.8}
        interp = ABGAnalyzer.interpret(readings)

        self.assertEqual(interp.ph_status, "Acidosis")
        self.assertIn("Respiratory Acidosis", interp.primary_disorder)
        self.assertIn("CO2 Retention", interp.paco2_status)
        self.assertIn("Respiratory Acidosis", interp.verdict)

    def test_critical_septic_shock(self):
        readings = {"ph": 7.15, "pao2": 65.0, "paco2": 30.0, "lactate": 8.5}
        interp = ABGAnalyzer.interpret(readings)

        self.assertEqual(interp.ph_status, "Acidosis")
        self.assertIn("Critical Lactic Acidosis", interp.lactate_status)
        self.assertIn("Hyperventilation", interp.compensation)
        self.assertEqual(interp.verdict, "CRITICAL - Septic Shock")


class TestABGHL7Formatting(unittest.TestCase):
    """Test HL7 ORU^R01 formatting with ABG_PANEL and brands."""

    def test_hl7_abg_panel_and_loinc(self):
        abg = ABGAnalyzer(bed_id="ICU_BED_04", patient_id="224606", brand="radiometer")
        readings = {"ph": 7.15, "pao2": 65.0, "paco2": 30.0, "lactate": 8.5}
        msg = abg.to_hl7(readings)
        raw = msg.to_string()

        # Check OBR panel
        self.assertIn("OBR|1|||ABG_PANEL|", raw)
        # Check sending application
        self.assertIn("RADIOMETER_ABL800", raw)

        # Check all 4 LOINC codes present
        expected_loinc = [
            "2744-1^ARTERIAL_PH^LN",
            "2703-7^PAO2^LN",
            "2019-8^PACO2^LN",
            "2524-7^LACTATE^LN",
        ]
        for code in expected_loinc:
            self.assertIn(code, raw)

        self.assertEqual(len(msg.observations), 4)

    def test_abnormal_flags_in_septic_shock(self):
        abg = ABGAnalyzer(scenario_name="septic")
        readings = abg.get_readings(progress=1.0)
        msg = abg.to_hl7(readings)

        flags = {obs.loinc_code.code: obs.abnormal_flag.value for obs in msg.observations}
        # pH: 7.15 -> LL (normal 7.35-7.45)
        self.assertEqual(flags["2744-1"], "LL")
        # Lactate: 8.5 -> HH (normal 0.5-2.0)
        self.assertEqual(flags["2524-7"], "HH")
        # PaCO2: ~30 -> L / LL (normal 35-45)
        self.assertIn(flags["2019-8"], ["L", "LL"])

    def test_alternative_brands(self):
        roche = ABGAnalyzer(brand="roche")
        self.assertIn("ROCHE_COBAS_B123", roche.to_hl7(roche.get_readings()).to_string())

        il_gem = ABGAnalyzer(brand="il_gem")
        self.assertIn("IL_GEM_PREMIER", il_gem.to_hl7(il_gem.get_readings()).to_string())


class TestABGScenarios(unittest.TestCase):
    """Test 4 clinical scenarios evolution."""

    def test_all_four_scenarios(self):
        for name in ["normal", "acidosis", "respiratory", "septic"]:
            traj = get_abg_scenario(name)
            start = traj.sample(0.0, add_noise=False)
            end = traj.sample(1.0, add_noise=False)
            self.assertIn("ph", start)
            self.assertIn("pao2", start)
            self.assertIn("paco2", start)
            self.assertIn("lactate", start)

            if name == "septic":
                self.assertLess(end["ph"], 7.20)
                self.assertGreater(end["lactate"], 8.0)


class TestABGMLLPIntegration(unittest.TestCase):
    """Test ABG streaming and on-demand transmission to MLLP Server."""

    def test_abg_on_demand_and_mllp(self):
        async def _test():
            server_port = 6791
            received = []

            def on_msg(raw):
                received.append(raw)
                return None

            server = MLLPServer(host="127.0.0.1", port=server_port, on_message=on_msg)
            await server.start()

            try:
                abg = ABGAnalyzer(bed_id="ICU_BED_04", brand="radiometer", scenario_name="septic")
                abg.connect(host="127.0.0.1", port=server_port)

                # Execute an on-demand blood gas draw
                readings, interp, msg = abg.sample_on_demand(progress=1.0)
                self.assertIn("CRITICAL", interp.verdict)

                ack = await abg._client.send_message(msg.to_string())
                self.assertIn("MSA|AA|", ack)
                self.assertEqual(len(received), 1)
                self.assertIn("2524-7^LACTATE^LN", received[0])

                abg.disconnect()
            finally:
                await server.stop()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
