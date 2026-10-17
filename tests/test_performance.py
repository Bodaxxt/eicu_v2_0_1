"""Performance benchmarks for ICU Guard v5.0."""
import os
import time
import pytest
import pandas as pd
from severity_agent.agent import SeverityAgent

BUNDLE_PATH = "e:/eicu_v2_0_1.sqlite3/model_artifacts/icu_guard_v4_2_agent_bundle.pkl"
COHORT_PATH = "e:/eicu_v2_0_1.sqlite3/multilabel_cohort.csv"

@pytest.fixture(scope="module")
def agent():
    if not os.path.exists(BUNDLE_PATH):
        pytest.skip("Bundle not present")
    return SeverityAgent(bundle_path=BUNDLE_PATH)

def test_single_patient_latency(agent):
    """Benchmark: Single patient full clinical assessment must complete in < 100ms."""
    pt = {
        "heartrate_mean": 95.0, "heartrate_max": 115.0, "heartrate_std": 12.0,
        "meanbp_min": 62.0, "sbp_min": 92.0, "sao2_min": 91.0,
        "resprate_max": 26.0, "creatinine_max": 1.8, "bun_max": 35.0,
        "gcs_min": 14.0, "lactate_max": 3.2, "temperature_max": 38.6,
        "wbc_max": 14.2, "platelets_min": 110.0, "hemoglobin_min": 9.2
    }

    # Warmup
    agent.full_assessment(pt, patient_id="BENCH-WARMUP")

    latencies = []
    for i in range(10):
        t0 = time.perf_counter()
        agent.full_assessment(pt, patient_id=f"BENCH-{i}")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

    avg_ms = sum(latencies) / len(latencies)
    print(f"\nAverage Single Patient Assessment Latency: {avg_ms:.2f} ms")
    assert avg_ms < 100.0, f"Assessment exceeded 100ms: {avg_ms:.2f}ms"

def test_batch_processing_throughput(agent):
    """Benchmark: Batch assessment of 1000 patients must finish in < 60 seconds (> 16 patients/sec)."""
    if not os.path.exists(COHORT_PATH):
        pytest.skip("Cohort not found")

    df = pd.read_csv(COHORT_PATH)
    # Replicate or slice to get 1000 patient records
    batch_1000 = pd.concat([df] * (1000 // len(df) + 1), ignore_index=True).iloc[:1000]

    t0 = time.perf_counter()
    results = agent.batch_assess(batch_1000)
    total_time = time.perf_counter() - t0

    throughput = len(results) / total_time
    print(f"\nBatch 1000 Patients Processed in: {total_time:.2f}s ({throughput:.1f} patients/sec)")
    assert len(results) == 1000
    assert total_time < 60.0, f"Batch 1000 exceeded 60s: {total_time:.2f}s"

def test_memory_footprint():
    """Benchmark: Process memory footprint should remain well below 500MB."""
    import psutil
    process = psutil.Process()
    mem_mb = process.memory_info().rss / (1024 * 1024)
    print(f"\nProcess Memory RSS: {mem_mb:.1f} MB")
    assert mem_mb < 500.0, f"Memory exceeded 500MB: {mem_mb:.1f} MB"
