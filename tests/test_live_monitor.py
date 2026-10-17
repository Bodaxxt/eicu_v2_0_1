"""
ICU Guard v5.0 — Live Monitor & Telemetry Streaming Tests
Phase 2: Comprehensive test suite for DataStreamer, LiveAnalyzer, AlertSystem,
Speed Controls, and Clinical Archetypes (STABLE vs CRITICAL Septic Shock).
"""

import pytest
import asyncio
from typing import Dict, Any

from dashboard.streaming.data_streamer import DataStreamer, StreamFrame
from dashboard.streaming.live_analyzer import LiveAnalyzer, LiveAnalysisResult, LiveAlert
from dashboard.components.alert_system import AlertSystem
from dashboard.components.vital_signs import get_vital_status, render_sparkline_svg
from dashboard.utils.constants import TIER_CRITICAL, TIER_HIGH, TIER_MODERATE, TIER_STABLE


# -----------------------------------------------------------------------------
# Fixtures: Clinical Archetypes
# -----------------------------------------------------------------------------
@pytest.fixture
def stable_patient_record() -> Dict[str, Any]:
    return {
        "id": "PT-STABLE-99",
        "tier": TIER_STABLE,
        "age": "45",
        "gender": "Female",
        "apache": "18",
        "heartrate_mean": 72.0,
        "heartrate_max": 82.0,
        "meanbp_min": 82.0,
        "sbp_min": 120.0,
        "resprate_max": 16.0,
        "temperature_max": 36.9,
        "sao2_min": 98.0,
        "gcs_min": 15.0,
        "lactate_max": 1.1,
    }


@pytest.fixture
def critical_shock_patient_record() -> Dict[str, Any]:
    return {
        "id": "PT-CRIT-99",
        "tier": TIER_CRITICAL,
        "age": "68",
        "gender": "Male",
        "apache": "92",
        "heartrate_mean": 124.0,
        "heartrate_max": 142.0,
        "meanbp_min": 50.0,
        "sbp_min": 78.0,
        "resprate_max": 36.0,
        "temperature_max": 39.5,
        "sao2_min": 82.0,
        "gcs_min": 10.0,
        "lactate_max": 6.2,
        "wbc_max": 22.0,
        "creatinine_max": 3.2,
    }


# -----------------------------------------------------------------------------
# 1. DataStreamer Unit Tests
# -----------------------------------------------------------------------------
def test_data_streamer_initialization(stable_patient_record):
    """Test streamer initializes with correct ticks, speed, and trajectory series."""
    streamer = DataStreamer(patient_record=stable_patient_record, total_ticks=30, speed=10.0)
    assert streamer.total_ticks == 30
    assert streamer.speed == 10.0
    assert len(streamer._series) == 30
    assert not streamer.is_running
    assert not streamer.is_paused


def test_data_streamer_speed_controls(stable_patient_record):
    """Test dynamic speed adjustment across supported multipliers."""
    streamer = DataStreamer(patient_record=stable_patient_record, total_ticks=30, speed=1.0)
    assert streamer.speed == 1.0

    streamer.set_speed(5.0)
    assert streamer.speed == 5.0

    streamer.set_speed(50.0)
    assert streamer.speed == 50.0


def test_data_streamer_pause_resume_stop(stable_patient_record):
    """Test pause, resume, and stop state transitions."""
    streamer = DataStreamer(patient_record=stable_patient_record, total_ticks=20)
    assert not streamer.is_paused
    assert not streamer.is_stopped

    streamer.pause()
    assert streamer.is_paused
    assert not streamer._pause_event.is_set()

    streamer.resume()
    assert not streamer.is_paused
    assert streamer._pause_event.is_set()

    streamer.stop()
    assert streamer.is_stopped


@pytest.mark.asyncio
async def test_data_streamer_execution_loop(stable_patient_record):
    """Test full async streaming loop execution and tick delivery."""
    frames_received = []

    def handle_tick(frame: StreamFrame):
        frames_received.append(frame)

    streamer = DataStreamer(
        patient_record=stable_patient_record,
        total_ticks=5,
        speed=50.0,  # 20ms per tick
        on_tick=handle_tick,
    )

    await streamer.run_loop()

    assert len(frames_received) == 5
    assert frames_received[0].tick == 1
    assert frames_received[-1].tick == 5
    assert frames_received[-1].is_terminal is True
    assert "hr" in frames_received[0].vitals
    assert "map" in frames_received[0].vitals


# -----------------------------------------------------------------------------
# 2. LiveAnalyzer Unit Tests
# -----------------------------------------------------------------------------
def test_live_analyzer_stable_patient(stable_patient_record):
    """Verify live analyzer correctly identifies STABLE archetype without false alarms."""
    analyzer = LiveAnalyzer(history_len=20)
    frame = StreamFrame(
        tick=1,
        total_ticks=20,
        progress_pct=5.0,
        timestamp_str="12:00:00",
        vitals={
            "hr": 74.0,
            "sbp": 120.0,
            "map": 82.0,
            "rr": 16.0,
            "temp": 36.8,
            "sao2": 98.0,
            "gcs": 15.0,
            "lactate": 1.1,
        },
        full_features=stable_patient_record,
    )

    result = analyzer.analyze_frame(frame)
    assert result.current_tier == TIER_STABLE
    assert result.trajectory == "STABLE"
    assert len(result.new_alerts) == 0
    assert len(result.vitals_history["hr"]) == 1


def test_live_analyzer_critical_shock_escalation(critical_shock_patient_record):
    """Verify live analyzer triggers CRITICAL tier, patterns, and alarms during shock."""
    analyzer = LiveAnalyzer(history_len=20)
    frame = StreamFrame(
        tick=10,
        total_ticks=30,
        progress_pct=33.3,
        timestamp_str="12:10:00",
        vitals={
            "hr": 138.0,  # Extreme Tachycardia
            "sbp": 74.0,
            "map": 51.0,  # Severe Shock MAP < 60
            "rr": 34.0,
            "temp": 39.4,
            "sao2": 82.0,  # Critical Hypoxemia
            "gcs": 10.0,
            "lactate": 5.8,
        },
        full_features=critical_shock_patient_record,
    )

    result = analyzer.analyze_frame(frame)
    assert result.current_tier in {TIER_CRITICAL, TIER_HIGH}
    assert result.trajectory in {"RAPID_DETERIORATION", "SLOW_DETERIORATION"}
    assert len(result.new_alerts) > 0

    # Ensure critical alerts fired for HR and MAP
    alert_titles = [a.title for a in result.new_alerts]
    assert any("Tachycardia" in t for t in alert_titles)
    assert any("Shock" in t or "MAP" in t or "Hypoxemia" in t for t in alert_titles)


def test_live_analyzer_trend_computation():
    """Verify trend direction and arrow indicators over rolling window."""
    analyzer = LiveAnalyzer(history_len=20)

    # Feed 5 progressively deteriorating ticks (rising HR, falling MAP)
    for i in range(5):
        frame = StreamFrame(
            tick=i + 1,
            total_ticks=20,
            progress_pct=float(i * 5),
            timestamp_str=f"12:0{i}:00",
            vitals={
                "hr": 80.0 + i * 8.0,      # 80 -> 112 (rising)
                "map": 85.0 - i * 6.0,     # 85 -> 61 (falling)
                "sao2": 99.0 - i * 2.0,    # 99 -> 91 (falling)
                "rr": 16.0 + i * 2.0,
                "temp": 37.0,
                "gcs": 15.0,
            },
            full_features={"patientunitstayid": "T1"},
        )
        res = analyzer.analyze_frame(frame)

    assert len(res.top_trends) >= 2
    metrics = {t.metric: t for t in res.top_trends}

    if "Heart Rate" in metrics:
        assert metrics["Heart Rate"].direction == "UP"
        assert metrics["Heart Rate"].arrow == "↗️"
        assert metrics["Heart Rate"].is_worsening is True

    if "Mean Arterial BP" in metrics:
        assert metrics["Mean Arterial BP"].direction == "DOWN"
        assert metrics["Mean Arterial BP"].arrow == "↘️"
        assert metrics["Mean Arterial BP"].is_worsening is True


# -----------------------------------------------------------------------------
# 3. AlertSystem & UI Component Helpers Tests
# -----------------------------------------------------------------------------
def test_alert_system_record_keeping():
    """Verify AlertSystem stores history correctly."""
    system = AlertSystem(enable_sound=False)
    alert = LiveAlert(
        id="a1",
        timestamp="14:00:00",
        severity="CRITICAL",
        color="#DC143C",
        title="Cardiac Arrhythmia",
        message="HR 145 bpm",
        icon="warning",
    )
    system.trigger_alert(alert)
    assert len(system.alert_history) == 1
    assert system.alert_history[0].id == "a1"


def test_vital_signs_color_and_status_mapping():
    """Verify clinical thresholds mapping to 🟢🟡🟠🔴."""
    # HR
    color_norm, _, _ = get_vital_status("hr", 75.0)
    assert color_norm == "#32CD32"

    color_crit, _, _ = get_vital_status("hr", 145.0)
    assert color_crit == "#DC143C"

    # MAP
    color_map_norm, _, _ = get_vital_status("map", 85.0)
    assert color_map_norm == "#32CD32"

    color_map_shock, _, _ = get_vital_status("map", 52.0)
    assert color_map_shock == "#DC143C"

    # SaO2
    color_o2_norm, _, _ = get_vital_status("sao2", 98.0)
    assert color_o2_norm == "#32CD32"

    color_o2_crit, _, _ = get_vital_status("sao2", 82.0)
    assert color_o2_crit == "#DC143C"


def test_sparkline_svg_rendering():
    """Verify inline SVG sparkline generator produces valid SVG markup."""
    svg = render_sparkline_svg([70.0, 75.0, 80.0, 85.0], "#32CD32")
    assert "<svg" in svg
    assert "<polyline" in svg
    assert "#32CD32" in svg
    assert "</svg>" in svg
