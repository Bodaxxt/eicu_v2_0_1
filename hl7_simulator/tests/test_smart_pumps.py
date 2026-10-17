"""
test_smart_pumps.py — Unit, Integration, and Clinical Tests for Smart Pumps
===========================================================================
Tests:
  1. 5 Infusion Drugs and LOINC mappings
  2. Clinical Interpretation (No vaso, Moderate, High/Refractory Shock)
  3. HL7 ORU^R01 generation with INFUSION_PARAMS
  4. 3 Pump Scenarios (no_vaso, moderate, high)
  5. MLLP Server integration and ACK receipt
"""

import asyncio
import unittest

from hl7_simulator.core.mllp_server import MLLPServer
from hl7_simulator.devices.smart_pumps import SmartPumps
from hl7_simulator.scenarios.pump_scenarios import get_pump_scenario


class TestPumpInterpretationEngine(unittest.TestCase):
    """Test the clinical evaluation of active infusions."""

    def test_no_vasopressors_stable(self):
        readings = {"norepinephrine": 0.0, "epinephrine": 0.0, "dopamine": 0.0, "propofol": 0.0, "fentanyl": 0.0}
        interp = SmartPumps.interpret(readings)

        self.assertIn("No Inotropic / Vasopressor Support", interp.vasopressor_status)
        self.assertIn("STABLE", interp.verdict)

    def test_moderate_shock(self):
        readings = {"norepinephrine": 0.10, "epinephrine": 0.0, "dopamine": 0.0, "propofol": 50.0, "fentanyl": 50.0}
        interp = SmartPumps.interpret(readings)

        self.assertIn("Moderate Hemodynamic Support", interp.vasopressor_status)
        self.assertIn("Moderate shock", interp.findings)
        self.assertEqual(interp.verdict, "HIGH - Moderate Shock")

    def test_refractory_shock_high_support(self):
        readings = {"norepinephrine": 0.50, "epinephrine": 0.30, "dopamine": 0.0, "propofol": 75.0, "fentanyl": 150.0}
        interp = SmartPumps.interpret(readings)

        self.assertIn("Refractory Shock", interp.vasopressor_status)
        self.assertIn("Deep Sedation", interp.sedation_status)
        self.assertEqual(interp.verdict, "CRITICAL - Refractory Shock")


class TestPumpHL7Formatting(unittest.TestCase):
    """Test HL7 ORU^R01 formatting with INFUSION_PARAMS and brands."""

    def test_all_five_drugs_present(self):
        pump = SmartPumps(bed_id="ICU_BED_04", patient_id="224606", brand="bbraun")
        readings = {
            "norepinephrine": 0.50,
            "epinephrine": 0.30,
            "dopamine": 5.0,
            "propofol": 75.0,
            "fentanyl": 150.0,
        }
        msg = pump.to_hl7(readings)
        raw = msg.to_string()

        self.assertIn("OBR|1|||INFUSION_PARAMS|", raw)
        self.assertIn("BBRAUN_SPACE", raw)

        expected_loinc = [
            "77137-8^NORADRENALINE_RATE^LN",
            "2272-6^EPINEPHRINE_RATE^LN",
            "2215-5^DOPAMINE_RATE^LN",
            "11451-2^PROPOFOL_RATE^LN",
            "11450-4^FENTANYL_RATE^LN",
        ]
        for code in expected_loinc:
            self.assertIn(code, raw)

        self.assertEqual(len(msg.observations), 5)

    def test_brands(self):
        alaris = SmartPumps(brand="alaris")
        self.assertIn("BD_ALARIS", alaris.to_hl7(alaris.get_readings()).to_string())

        fresenius = SmartPumps(brand="fresenius")
        self.assertIn("FRESENIUS_AGILIA", fresenius.to_hl7(fresenius.get_readings()).to_string())


class TestPumpScenarios(unittest.TestCase):
    """Test 3 pump scenarios."""

    def test_all_three_scenarios(self):
        for name in ["no_vaso", "moderate", "high"]:
            traj = get_pump_scenario(name)
            start = traj.sample(0.0, add_noise=False)
            end = traj.sample(1.0, add_noise=False)

            self.assertEqual(len(start), 5)
            self.assertEqual(len(end), 5)

            if name == "high":
                self.assertAlmostEqual(end["norepinephrine"], 0.50, delta=0.05)
                self.assertAlmostEqual(end["epinephrine"], 0.30, delta=0.05)


class TestPumpMLLPIntegration(unittest.TestCase):
    """Test on-demand transmission to MLLP Server."""

    def test_on_demand_pump_mllp(self):
        async def _test():
            server_port = 6793
            received = []

            def on_msg(raw):
                received.append(raw)
                return None

            server = MLLPServer(host="127.0.0.1", port=server_port, on_message=on_msg)
            await server.start()

            try:
                pump = SmartPumps(bed_id="ICU_BED_04", brand="bbraun", scenario_name="high")
                pump.connect(host="127.0.0.1", port=server_port)

                readings, interp, msg = pump.sample_on_demand(progress=1.0)
                self.assertIn("Refractory Shock", interp.verdict)

                ack = await pump._client.send_message(msg.to_string())
                self.assertIn("MSA|AA|", ack)
                self.assertEqual(len(received), 1)
                self.assertIn("77137-8^NORADRENALINE_RATE^LN", received[0])

                pump.disconnect()
            finally:
                await server.stop()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
