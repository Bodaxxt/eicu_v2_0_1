"""
test_continuous_prediction.py — Unit & Integration Tests for Continuous Prediction Engine
========================================================================================
Validates:
1. PredictionHistory (SQLite persistence, delta computation, cache retrieval)
2. TierChangeDetector (Non-downgrading semantics, escalation alerts)
3. TrajectoryAnalyzer (Velocity calculation, trajectory types, time-to-critical)
4. PredictionScheduler (10-hour simulation, 120 periodic predictions, 3 tier transitions)
"""

import asyncio
import pytest
from severity_agent.hl7.history import PredictionHistory, PredictionRecord
from severity_agent.hl7.tier_detector import TierChangeDetector, TierChangeEvent
from severity_agent.hl7.trajectory import TrajectoryAnalyzer, TrajectoryResult
from severity_agent.hl7.scheduler import PredictionScheduler
from severity_agent.hl7.live_timeline import LiveTimeline


# -----------------------------------------------------------------------------
# 1. PredictionHistory Tests
# -----------------------------------------------------------------------------
class TestPredictionHistory:
    def test_add_and_retrieve_history(self):
        history = PredictionHistory(db_path=":memory:")
        pid = "TEST_PATIENT_01"

        assess_1 = {
            "probabilities": {"mortality_risk": 0.08, "deterioration_risk": 0.15, "severe_risk": 0.12},
            "severity_tier": "STABLE",
            "patterns": [],
        }
        rec_1 = history.add_prediction(pid, assess_1, sim_time_minutes=0.0)

        assert rec_1.patient_id == pid
        assert rec_1.sim_time_minutes == 0.0
        assert rec_1.sim_time_str == "00:00"
        assert rec_1.mortality_risk == 0.08
        assert rec_1.delta_mortality == 0.0

        assess_2 = {
            "probabilities": {"mortality_risk": 0.10, "deterioration_risk": 0.20, "severe_risk": 0.16},
            "severity_tier": "MODERATE",
            "patterns": [{"name": "Early Sepsis", "detected": True}],
        }
        rec_2 = history.add_prediction(pid, assess_2, sim_time_minutes=5.0)

        assert rec_2.sim_time_str == "00:05"
        assert round(rec_2.delta_mortality, 4) == 0.02
        assert round(rec_2.delta_deterioration, 4) == 0.05
        assert round(rec_2.delta_severe, 4) == 0.04
        assert len(rec_2.active_patterns) == 1

        # Check chronological list
        records = history.get_history(pid)
        assert len(records) == 2
        assert records[0].id == rec_1.id
        assert records[1].id == rec_2.id

        # Check deltas
        deltas = history.get_deltas(pid)
        assert round(deltas["total_deterioration"], 4) == 0.05

        # Clear
        history.clear_history(pid)
        assert len(history.get_history(pid)) == 0


# -----------------------------------------------------------------------------
# 2. TierChangeDetector Tests
# -----------------------------------------------------------------------------
class TestTierChangeDetector:
    def test_tier_escalation_and_non_downgrading(self):
        detector = TierChangeDetector(non_downgrading=True)
        pid = "TEST_PATIENT_02"
        events: list[TierChangeEvent] = []
        detector.register_listener(events.append)

        # Baseline: STABLE
        t1, evt1 = detector.evaluate(pid, "STABLE", {"deterioration_risk": 0.15}, 0.0, "00:00")
        assert t1 == "STABLE"
        assert evt1 is None

        # Escalation 1: STABLE -> MODERATE at 04:00 (240 min)
        t2, evt2 = detector.evaluate(pid, "MODERATE", {"deterioration_risk": 0.25}, 240.0, "04:00")
        assert t2 == "MODERATE"
        assert evt2 is not None
        assert evt2.previous_tier == "STABLE"
        assert evt2.new_tier == "MODERATE"
        assert evt2.sim_time_str == "04:00"

        # Escalation 2: MODERATE -> HIGH at 08:00 (480 min)
        t3, evt3 = detector.evaluate(pid, "HIGH", {"deterioration_risk": 0.55}, 480.0, "08:00")
        assert t3 == "HIGH"
        assert evt3 is not None
        assert evt3.previous_tier == "MODERATE"
        assert evt3.new_tier == "HIGH"

        # Escalation 3: HIGH -> CRITICAL at 10:00 (600 min)
        t4, evt4 = detector.evaluate(pid, "CRITICAL", {"deterioration_risk": 0.88}, 600.0, "10:00")
        assert t4 == "CRITICAL"
        assert evt4 is not None
        assert evt4.previous_tier == "HIGH"
        assert evt4.new_tier == "CRITICAL"

        # Non-downgrading test: Attempt to downgrade to STABLE
        t5, evt5 = detector.evaluate(pid, "STABLE", {"deterioration_risk": 0.20}, 605.0, "10:05")
        assert t5 == "CRITICAL"  # Must stay CRITICAL!
        assert evt5 is None      # No new escalation event

        # Verify 3 events logged
        assert len(events) == 3
        assert len(detector.get_tier_changes(pid)) == 3


# -----------------------------------------------------------------------------
# 3. TrajectoryAnalyzer Tests
# -----------------------------------------------------------------------------
class TestTrajectoryAnalyzer:
    def test_trajectory_types(self):
        # 1. Rapid deterioration (steep rise)
        history_rapid = [
            PredictionRecord(sim_time_minutes=0.0, deterioration_risk=0.20, mortality_risk=0.10, severe_risk=0.15),
            PredictionRecord(sim_time_minutes=30.0, deterioration_risk=0.35, mortality_risk=0.18, severe_risk=0.25),
            PredictionRecord(sim_time_minutes=60.0, deterioration_risk=0.55, mortality_risk=0.28, severe_risk=0.40),
        ]
        res_rapid = TrajectoryAnalyzer.analyze(history_rapid)
        assert res_rapid.trajectory_type == "RAPID_DETERIORATION"
        assert res_rapid.rate_of_change_per_hour > 0.10
        assert res_rapid.time_to_critical_minutes is not None

        # 2. Stable
        history_stable = [
            PredictionRecord(sim_time_minutes=0.0, deterioration_risk=0.20, mortality_risk=0.10, severe_risk=0.15),
            PredictionRecord(sim_time_minutes=30.0, deterioration_risk=0.21, mortality_risk=0.10, severe_risk=0.15),
            PredictionRecord(sim_time_minutes=60.0, deterioration_risk=0.20, mortality_risk=0.11, severe_risk=0.16),
        ]
        res_stable = TrajectoryAnalyzer.analyze(history_stable)
        assert res_stable.trajectory_type == "STABLE"

        # 3. Improving
        history_impr = [
            PredictionRecord(sim_time_minutes=0.0, deterioration_risk=0.60, mortality_risk=0.30, severe_risk=0.45),
            PredictionRecord(sim_time_minutes=30.0, deterioration_risk=0.45, mortality_risk=0.22, severe_risk=0.35),
            PredictionRecord(sim_time_minutes=60.0, deterioration_risk=0.30, mortality_risk=0.15, severe_risk=0.25),
        ]
        res_impr = TrajectoryAnalyzer.analyze(history_impr)
        assert res_impr.trajectory_type == "IMPROVING"
        assert res_impr.rate_of_change_per_hour < -0.10


# -----------------------------------------------------------------------------
# 4. End-to-End Simulation: 10 Hours, 120 Predictions, 3 Tier Changes
# -----------------------------------------------------------------------------
class TestPredictionSchedulerSimulation:
    @pytest.mark.asyncio
    async def test_10_hour_simulation_120_predictions_3_tier_changes(self):
        history = PredictionHistory(db_path=":memory:")
        tier_detector = TierChangeDetector(non_downgrading=True)
        timeline = LiveTimeline()

        scheduler = PredictionScheduler(
            history=history,
            tier_detector=tier_detector,
            timeline=timeline,
            interval_sim_minutes=5.0,
            speed_multiplier=5000.0,  # Fast test execution
        )

        patient_id = "PATIENT_SIM_10H"

        # Run 120 steps representing 10 hours (600 minutes / 5 minutes = 120 predictions)
        for i in range(120):
            sim_time = i * 5.0
            await scheduler._execute_prediction_step(patient_id, sim_time)

        # 1. Verify 120 predictions recorded
        records = history.get_history(patient_id)
        assert len(records) == 120, f"Expected 120 predictions, got {len(records)}"

        # 2. Verify start and end times
        assert records[0].sim_time_str == "00:00"
        assert records[-1].sim_time_str == "09:55"

        # 3. Verify risk probability evolution
        # Initial state (nominal)
        assert records[0].mortality_risk <= 0.15
        assert records[0].deterioration_risk <= 0.25

        # Final state (critical shock decompensation)
        assert records[-1].deterioration_risk >= 0.80
        assert records[-1].mortality_risk >= 0.50
        assert records[-1].effective_tier == "CRITICAL"

        # 4. Verify exactly 3 Tier Transitions occurred
        tier_changes = tier_detector.get_tier_changes(patient_id)
        assert len(tier_changes) == 3, f"Expected 3 tier changes, got {len(tier_changes)}"

        # Verify the 3 transitions
        t1, t2, t3 = tier_changes
        assert t1.previous_tier == "STABLE" and t1.new_tier == "MODERATE"
        assert t2.previous_tier == "MODERATE" and t2.new_tier == "HIGH"
        assert t3.previous_tier == "HIGH" and t3.new_tier == "CRITICAL"

        # 5. Verify Timeline recorded events
        events = timeline.get_events(patient_id)
        assert len(events) >= 120
