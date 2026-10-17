"""
test_central_lab.py — Unit, Integration, and Clinical Tests for Central Lab
===========================================================================
Tests:
  1. 10 Core laboratory analytes and LOINC mapping
  2. Clinical Interpretation Engine (KDIGO AKI, ISTH DIC, Sepsis, Normal)
  3. HL7 ORU^R01 formatting with CHEM_PANEL
  4. 4 Clinical Lab Scenarios (Normal, Renal Failure, Sepsis, DIC)
  5. MLLP Server integration and ACK receipt
"""

import asyncio
import unittest

from hl7_simulator.core.mllp_server import MLLPServer
from hl7_simulator.devices.central_lab import CentralLab
from hl7_simulator.scenarios.lab_scenarios import get_lab_scenario


class TestLabInterpretationEngine(unittest.TestCase):
    """Test the clinical evaluation of laboratory findings."""

    def test_normal_labs(self):
        readings = {
            "creatinine": 0.9,
            "bun": 14.0,
            "wbc": 7.2,
            "platelets": 250.0,
            "hemoglobin": 14.0,
            "glucose": 90.0,
            "sodium": 140.0,
            "potassium": 4.1,
            "inr": 1.0,
            "ptt": 29.0,
        }
        interp = CentralLab.interpret(readings)

        self.assertEqual(interp.aki_stage, "Normal Renal Function")
        self.assertEqual(interp.hematology_status, "Normal Blood Counts")
        self.assertEqual(interp.coagulation_status, "Normal Hemostasis Profile")
        self.assertIn("STABLE", interp.verdict)

    def test_renal_failure_kdigo_aki_stage_2(self):
        readings = {
            "creatinine": 2.8,
            "bun": 52.0,
            "wbc": 9.5,
            "platelets": 200.0,
            "hemoglobin": 11.5,
            "glucose": 120.0,
            "sodium": 136.0,
            "potassium": 5.3,
            "inr": 1.1,
            "ptt": 31.0,
        }
        interp = CentralLab.interpret(readings, baseline_creatinine=1.0)

        self.assertEqual(interp.aki_stage, "AKI Stage 2 (KDIGO)")
        self.assertGreaterEqual(interp.bun_cr_ratio, 18.0)
        self.assertIn("Hyperkalemia", interp.electrolyte_status)
        self.assertIn("WARNING - AKI Stage 2", interp.verdict)

    def test_sepsis_pattern(self):
        readings = {
            "creatinine": 1.8,
            "bun": 32.0,
            "wbc": 18.5,
            "platelets": 95.0,
            "hemoglobin": 9.8,
            "glucose": 180.0,
            "sodium": 136.0,
            "potassium": 4.4,
            "inr": 1.7,
            "ptt": 42.0,
        }
        interp = CentralLab.interpret(readings)

        self.assertIn("Leukocytosis", interp.hematology_status)
        self.assertIn("Thrombocytopenia", interp.hematology_status)
        self.assertIn("Sepsis with Organ Dysfunction", interp.verdict)

    def test_dic_pattern_isth(self):
        readings = {
            "creatinine": 2.4,
            "bun": 46.0,
            "wbc": 20.0,
            "platelets": 45.0,
            "hemoglobin": 7.8,
            "glucose": 185.0,
            "sodium": 133.0,
            "potassium": 4.8,
            "inr": 2.5,
            "ptt": 65.0,
        }
        interp = CentralLab.interpret(readings)

        self.assertIn("Severe Thrombocytopenia", interp.hematology_status)
        self.assertIn("Overt Disseminated Intravascular Coagulation", interp.coagulation_status)
        self.assertEqual(interp.verdict, "CRITICAL - Overt DIC (ISTH criteria)")


class TestLabHL7Formatting(unittest.TestCase):
    """Test HL7 ORU^R01 formatting with CHEM_PANEL and 10 analytes."""

    def test_all_ten_parameters_present(self):
        lab = CentralLab(bed_id="ICU_BED_04", patient_id="224606", brand="roche")
        readings = {
            "creatinine": 2.8,
            "bun": 52.0,
            "wbc": 18.5,
            "platelets": 95.0,
            "hemoglobin": 9.2,
            "glucose": 180.0,
            "sodium": 138.0,
            "potassium": 4.2,
            "inr": 1.8,
            "ptt": 45.0,
        }
        msg = lab.to_hl7(readings)
        raw = msg.to_string()

        # Check OBR panel and sending application
        self.assertIn("OBR|1|||CHEM_PANEL|", raw)
        self.assertIn("ROCHE_COBAS_8000", raw)

        expected_loinc = [
            "2160-0^CREATININE^LN",
            "3094-0^BUN^LN",
            "6690-2^WBC^LN",
            "777-3^PLATELETS^LN",
            "718-7^HEMOGLOBIN^LN",
            "2345-7^GLUCOSE^LN",
            "2951-2^SODIUM^LN",
            "2823-3^POTASSIUM^LN",
            "6301-6^INR^LN",
            "14979-9^PTT^LN",
        ]
        for code in expected_loinc:
            self.assertIn(code, raw)

        self.assertEqual(len(msg.observations), 10)

    def test_alternative_brands(self):
        abbott = CentralLab(brand="abbott")
        self.assertIn("ABBOTT_ARCHITECT", abbott.to_hl7(abbott.get_readings()).to_string())

        siemens = CentralLab(brand="siemens")
        self.assertIn("SIEMENS_ATELLICA", siemens.to_hl7(siemens.get_readings()).to_string())

    def test_abnormal_flags(self):
        lab = CentralLab(scenario_name="dic")
        readings = lab.get_readings(progress=1.0)
        msg = lab.to_hl7(readings)

        flags = {obs.loinc_code.code: obs.abnormal_flag.value for obs in msg.observations}
        # Platelets: ~45 -> LL (normal 150-400)
        self.assertEqual(flags["777-3"], "LL")
        # INR: ~2.5 -> HH (normal 0.8-1.2)
        self.assertEqual(flags["6301-6"], "HH")
        # WBC: ~21 -> HH (normal 4-11)
        self.assertEqual(flags["6690-2"], "HH")


class TestLabScenarios(unittest.TestCase):
    """Test 4 clinical laboratory trajectories."""

    def test_all_four_scenarios(self):
        for name in ["normal", "renal", "sepsis", "dic"]:
            traj = get_lab_scenario(name)
            start = traj.sample(0.0, add_noise=False)
            end = traj.sample(1.0, add_noise=False)

            self.assertEqual(len(start), 10)
            self.assertEqual(len(end), 10)

            if name == "renal":
                self.assertGreaterEqual(end["creatinine"], 2.7)
            elif name == "dic":
                self.assertLessEqual(end["platelets"], 50.0)


class TestLabMLLPIntegration(unittest.TestCase):
    """Test on-demand transmission to MLLP Server."""

    def test_on_demand_lab_mllp(self):
        async def _test():
            server_port = 6792
            received = []

            def on_msg(raw):
                received.append(raw)
                return None

            server = MLLPServer(host="127.0.0.1", port=server_port, on_message=on_msg)
            await server.start()

            try:
                lab = CentralLab(bed_id="ICU_BED_04", brand="roche", scenario_name="renal")
                lab.connect(host="127.0.0.1", port=server_port)

                readings, interp, msg = lab.sample_on_demand(progress=1.0)
                self.assertIn("AKI Stage 2", interp.verdict)

                ack = await lab._client.send_message(msg.to_string())
                self.assertIn("MSA|AA|", ack)
                self.assertEqual(len(received), 1)
                self.assertIn("2160-0^CREATININE^LN", received[0])

                lab.disconnect()
            finally:
                await server.stop()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
