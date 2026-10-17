"""
test_ventilator.py — Unit, Integration, and Clinical Tests for Ventilator
=========================================================================
Tests:
  1. 6 Ventilator Parameters and LOINC mappings
  2. Clinical Interpretation (Spontaneous, Standard, Severe ARDS)
  3. HL7 ORU^R01 generation with VENTILATOR_PARAMS
  4. 3 Ventilator Scenarios (no_vent, moderate, severe)
  5. MLLP Server integration and ACK receipt
"""

import asyncio
import unittest

from hl7_simulator.core.mllp_server import MLLPServer
from hl7_simulator.devices.ventilator import Ventilator
from hl7_simulator.scenarios.ventilator_scenarios import get_ventilator_scenario


class TestVentilatorInterpretationEngine(unittest.TestCase):
    """Test the clinical evaluation of mechanical ventilation and ARDS."""

    def test_spontaneous_breathing_extubated(self):
        readings = {"mode": "SPONT", "fio2": 21.0, "peep": 0.0, "tidal_volume": 0.0, "respiratory_rate": 0.0, "peak_pressure": 0.0}
        interp = Ventilator.interpret(readings)

        self.assertIn("Spontaneous", interp.oxygenation_support)
        self.assertIn("STABLE", interp.verdict)

    def test_moderate_standard_ventilation(self):
        readings = {"mode": "VC", "fio2": 40.0, "peep": 8.0, "tidal_volume": 500.0, "respiratory_rate": 16.0, "peak_pressure": 22.0}
        interp = Ventilator.interpret(readings)

        self.assertIn("Moderate Ventilation Support", interp.oxygenation_support)
        self.assertIn("Standard Tidal Volume", interp.lung_protective_status)
        self.assertEqual(interp.verdict, "MODERATE - Standard Mechanical Ventilation")

    def test_severe_ards_lung_protective(self):
        readings = {"mode": "PC", "fio2": 80.0, "peep": 14.0, "tidal_volume": 400.0, "respiratory_rate": 24.0, "peak_pressure": 32.0}
        interp = Ventilator.interpret(readings)

        self.assertIn("Severe Hypoxemia Support", interp.oxygenation_support)
        self.assertIn("Lung-Protective Strategy", interp.lung_protective_status)
        self.assertIn("Barotrauma Risk", interp.airway_pressure_status)
        self.assertEqual(interp.verdict, "CRITICAL - Severe ARDS")


class TestVentilatorHL7Formatting(unittest.TestCase):
    """Test HL7 ORU^R01 formatting with VENTILATOR_PARAMS and brands."""

    def test_parameters_present(self):
        vent = Ventilator(bed_id="ICU_BED_04", patient_id="224606", brand="draeger")
        readings = {
            "mode": "PC",
            "fio2": 80.0,
            "peep": 14.0,
            "tidal_volume": 400.0,
            "respiratory_rate": 24.0,
            "peak_pressure": 32.0,
        }
        msg = vent.to_hl7(readings)
        raw = msg.to_string()

        self.assertIn("OBR|1|||VENTILATOR_PARAMS|", raw)
        self.assertIn("DRAEGER_EVITA", raw)

        expected_loinc = [
            "3150-0^FIO2^LN",
            "76248-4^PEEP^LN",
            "76222-9^TIDAL_VOLUME^LN",
            "9279-1^RESP_RATE^LN",
            "76251-8^PEAK_PRESSURE^LN",
        ]
        for code in expected_loinc:
            self.assertIn(code, raw)

    def test_brands(self):
        hamilton = Ventilator(brand="hamilton")
        self.assertIn("HAMILTON_MEDICAL", hamilton.to_hl7(hamilton.get_readings()).to_string())

        puritan = Ventilator(brand="puritan")
        self.assertIn("PURITAN_BENNETT_980", puritan.to_hl7(puritan.get_readings()).to_string())


class TestVentilatorScenarios(unittest.TestCase):
    """Test 3 ventilator scenarios."""

    def test_all_three_scenarios(self):
        for name in ["no_vent", "moderate", "severe"]:
            traj = get_ventilator_scenario(name)
            start = traj.sample(0.0, add_noise=False)
            end = traj.sample(1.0, add_noise=False)

            self.assertIn("fio2", start)
            self.assertIn("peep", start)
            self.assertIn("tidal_volume", start)

            if name == "severe":
                self.assertGreaterEqual(end["fio2"], 75.0)
                self.assertGreaterEqual(end["peep"], 13.0)


class TestVentilatorMLLPIntegration(unittest.TestCase):
    """Test on-demand transmission to MLLP Server."""

    def test_on_demand_vent_mllp(self):
        async def _test():
            server_port = 6794
            received = []

            def on_msg(raw):
                received.append(raw)
                return None

            server = MLLPServer(host="127.0.0.1", port=server_port, on_message=on_msg)
            await server.start()

            try:
                vent = Ventilator(bed_id="ICU_BED_04", brand="draeger", scenario_name="severe")
                vent.connect(host="127.0.0.1", port=server_port)

                readings, interp, msg = vent.sample_on_demand(progress=1.0)
                self.assertIn("Severe ARDS", interp.verdict)

                ack = await vent._client.send_message(msg.to_string())
                self.assertIn("MSA|AA|", ack)
                self.assertEqual(len(received), 1)
                self.assertIn("3150-0^FIO2^LN", received[0])

                vent.disconnect()
            finally:
                await server.stop()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
