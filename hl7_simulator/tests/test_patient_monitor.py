"""
test_patient_monitor.py — Unit, Integration, and Scenario Tests for Patient Monitor
===================================================================================
Tests:
  1. BaseDevice lifecycle and interpolation
  2. PatientMonitor 7-vital extraction and brand support (Philips, GE, Mindray)
  3. HL7 ORU^R01 structure and LOINC mapping
  4. Abnormal flags calculation (LL, L, N, H, HH)
  5. 3 Clinical scenarios (Stable, Deteriorating, Critical Septic Shock)
  6. MLLP streaming and ACK confirmation
"""

import asyncio
import unittest
from pathlib import Path

from hl7_simulator.core.mllp_server import MLLPServer
from hl7_simulator.devices.base_device import BaseDevice
from hl7_simulator.devices.patient_monitor import PatientMonitor
from hl7_simulator.scenarios.patient_monitor_scenarios import (
    get_scenario_trajectory,
    load_cohort_patient_trajectory,
)


class TestVitalsCalculationAndTrajectories(unittest.TestCase):
    """Test interpolation, noise, and physiological range clamping."""

    def test_stable_scenario_invariants(self):
        traj = get_scenario_trajectory("stable")
        # Sample at start, middle, end without noise
        start = traj.sample(0.0, add_noise=False)
        mid = traj.sample(0.5, add_noise=False)
        end = traj.sample(1.0, add_noise=False)

        self.assertAlmostEqual(start["heart_rate"], 78.0, delta=0.5)
        self.assertAlmostEqual(end["heart_rate"], 78.0, delta=0.5)
        self.assertAlmostEqual(start["sbp"], 120.0, delta=0.5)
        self.assertAlmostEqual(end["spo2"], 98.0, delta=0.5)

    def test_deteriorating_scenario_evolution(self):
        traj = get_scenario_trajectory("deteriorating")
        start = traj.sample(0.0, add_noise=False)
        end = traj.sample(1.0, add_noise=False)

        # Heart rate should increase
        self.assertLess(start["heart_rate"], end["heart_rate"])
        self.assertAlmostEqual(end["heart_rate"], 110.0, delta=1.0)

        # Blood pressure & SpO2 should decline
        self.assertGreater(start["sbp"], end["sbp"])
        self.assertGreater(start["spo2"], end["spo2"])
        self.assertAlmostEqual(end["spo2"], 88.0, delta=1.0)

        # Temperature should rise
        self.assertLess(start["temperature"], end["temperature"])

    def test_critical_septic_shock_evolution(self):
        traj = get_scenario_trajectory("critical")
        start = traj.sample(0.0, add_noise=False)
        end = traj.sample(1.0, add_noise=False)

        # Severe tachycardia
        self.assertGreaterEqual(end["heart_rate"], 125.0)
        # Severe hypotension (MAP drops to ~46)
        self.assertLessEqual(end["mean_bp"], 50.0)
        # Severe hypoxia
        self.assertLessEqual(end["spo2"], 85.0)
        # High fever
        self.assertGreaterEqual(end["temperature"], 39.0)

    def test_linear_interpolation_util(self):
        val = BaseDevice.linear_interpolate(10.0, 20.0, 0.5)
        self.assertEqual(val, 15.0)
        # Clamping check
        self.assertEqual(BaseDevice.linear_interpolate(10.0, 20.0, -0.5), 10.0)
        self.assertEqual(BaseDevice.linear_interpolate(10.0, 20.0, 1.5), 20.0)


class TestPatientMonitorHL7(unittest.TestCase):
    """Test HL7 message structure, brands, and abnormal flags."""

    def test_all_seven_vitals_present_in_hl7(self):
        monitor = PatientMonitor(bed_id="ICU_BED_04", patient_id="224606", brand="philips")
        readings = monitor.get_readings(progress=0.0)
        msg = monitor.to_hl7(readings)
        raw = msg.to_string()

        # Check required LOINC codes
        expected_loinc = [
            "8867-4^HEART_RATE^LN",
            "8480-6^SYSTOLIC_BP^LN",
            "8462-4^DIASTOLIC_BP^LN",
            "8478-0^MEAN_BP^LN",
            "9279-1^RESP_RATE^LN",
            "2708-6^OXYGEN_SAT^LN",
            "8310-5^TEMPERATURE^LN",
        ]
        for code in expected_loinc:
            self.assertIn(code, raw)

        self.assertEqual(len(msg.observations), 7)

    def test_brands_configuration(self):
        philips = PatientMonitor(brand="philips")
        self.assertIn("PHILIPS_INTELLIVUE", philips.to_hl7(philips.get_readings()).to_string())

        ge = PatientMonitor(brand="ge")
        self.assertIn("GE_CARESCAPE", ge.to_hl7(ge.get_readings()).to_string())

        mindray = PatientMonitor(brand="mindray")
        self.assertIn("MINDRAY_BENEVISION", mindray.to_hl7(mindray.get_readings()).to_string())

    def test_abnormal_flags_in_shock(self):
        monitor = PatientMonitor(scenario_name="critical")
        # Sample at end of septic shock
        readings = monitor.trajectory.sample(1.0, add_noise=False)
        msg = monitor.to_hl7(readings)

        flags = {obs.loinc_code.code: obs.abnormal_flag.value for obs in msg.observations}

        # Heart rate: 128 bpm -> High / Critical High
        self.assertIn(flags["8867-4"], ["H", "HH"])
        # MAP: 46 mmHg -> Low / Critical Low (normal 65-110)
        self.assertIn(flags["8478-0"], ["L", "LL"])
        # SpO2: 83% -> Critical Low (normal 95-100)
        self.assertEqual(flags["2708-6"], "LL")
        # Temperature: 39.4C -> Critical High
        self.assertEqual(flags["8310-5"], "HH")


class TestPatientMonitorIntegration(unittest.TestCase):
    """Integration test: Stream over MLLP TCP Server."""

    def test_streaming_to_mllp_server(self):
        async def _test():
            server_port = 6789
            received = []

            def on_msg(raw):
                received.append(raw)
                return None

            server = MLLPServer(host="127.0.0.1", port=server_port, on_message=on_msg)
            await server.start()

            try:
                monitor = PatientMonitor(bed_id="BED_TEST", brand="philips", scenario_name="stable")
                monitor.connect(host="127.0.0.1", port=server_port)

                # Stream 3 ticks with high time dilation
                messages = []
                async for msg, ack in monitor.stream(
                    duration_minutes=1.0,
                    interval_seconds=30.0,
                    time_dilation=1000.0,
                ):
                    messages.append(msg)
                    self.assertIsNotNone(ack)
                    self.assertIn("MSA|AA|", ack)

                self.assertGreaterEqual(len(messages), 2)
                self.assertEqual(len(received), len(messages))
                monitor.disconnect()
            finally:
                await server.stop()

        asyncio.run(_test())

    def test_cohort_loading(self):
        cohort_csv = Path("multilabel_cohort.csv")
        if cohort_csv.exists():
            traj = load_cohort_patient_trajectory(cohort_csv, patient_id="224606")
            readings = traj.sample(0.5)
            self.assertIn("heart_rate", readings)
            self.assertIn("mean_bp", readings)


if __name__ == "__main__":
    unittest.main()
