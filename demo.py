"""
ICU Guard v4.2 — Severity Agent Real-World Demonstration
========================================================
Runs the SeverityAgent on 3 diverse real patients from the eICU-CRD cohort:
1. Critical Decompensation Candidate (Acute Shock / High Deterioration)
2. Moderate-to-Severe Organ Burden (Multi-System Failure / Sepsis)
3. Stable / Low Risk ICU Patient (Routine Surveillance)
"""

import sys, os
import pandas as pd

# Set UTF-8 encoding for bilingual Arabic/English terminal output
sys.stdout.reconfigure(encoding='utf-8')

from severity_agent.agent import SeverityAgent

COHORT_PATH = "e:/eicu_v2_0_1.sqlite3/multilabel_cohort.csv"
BUNDLE_PATH = "e:/eicu_v2_0_1.sqlite3/model_artifacts/icu_guard_v4_2_agent_bundle.pkl"

def main():
    print("=" * 80)
    print("  ICU GUARD v4.2 — SEVERITY AGENT LIVE DEMONSTRATION")
    print("=" * 80)
    
    # 1. Initialize Agent
    print(f"\n[1/3] Initializing SeverityAgent from bundle...")
    agent = SeverityAgent(bundle_path=BUNDLE_PATH)
    print(f"      Agent version: {agent.version}")
    print(f"      Models verified: {list(agent.models.keys())}")

    # 2. Load Cohort and Select 3 Real Patients
    print(f"\n[2/3] Loading real patients from {COHORT_PATH}...")
    df = pd.read_csv(COHORT_PATH)
    
    # Patient 1: Critical shock candidate (Decompensation = 1 & Mortality = 1)
    crit_patient = df[(df['y_deterioration'] == 1) & (df['y_mortality'] == 1)].iloc[0]

    # Patient 2: Severe organ failure candidate
    mod_patient = df[(df['y_severe'] == 1) & (df['y_deterioration'] == 0)].iloc[0]

    # Patient 3: Truly stable ICU patient
    stable_candidates = df[
        (df['y_mortality'] == 0) & 
        (df['y_deterioration'] == 0) & 
        (df['y_severe'] == 0) &
        (df['meanbp_min'] >= 70) &
        (df['sbp_min'] >= 100) &
        (df['sao2_min'] >= 95)
    ]
    stable_patient = stable_candidates.iloc[0] if len(stable_candidates) > 0 else df.iloc[195]

    cases = [
        ("CASE 1: ACUTE DECOMPENSATION & CRITICAL SHOCK", crit_patient),
        ("CASE 2: SEVERE ORGAN BURDEN / MULTI-ORGAN FAILURE", mod_patient),
        ("CASE 3: UNCOMPLICATED STABLE ICU ADMISSION", stable_patient)
    ]

    # 3. Execute Full Assessment
    print(f"\n[3/3] Executing clinical inference for 3 real ICU cases...\n")

    for case_title, patient_series in cases:
        pid = patient_series.get('patientunitstayid', 'Unknown-ID')
        p_dict = patient_series.to_dict()

        assessment = agent.full_assessment(p_dict, patient_id=pid)

        print("\n" + "#" * 80)
        print(f"  {case_title} (Patient ID: {pid})")
        print("#" * 80)
        
        # Display key bedside vitals
        hr = p_dict.get('heartrate_mean', 'N/A')
        bp = p_dict.get('meanbp_min', 'N/A')
        si = p_dict.get('shock_index_max', 'N/A')
        cr = p_dict.get('creatinine_max', 'N/A')
        gcs = p_dict.get('gcs_min', 'N/A')
        print(f"Bedside Vitals: HR Mean={hr} | MAP Min={bp} | Max Shock Index={si} | Cr Max={cr} | GCS Min={gcs}")

        # English Clinical Report
        print("\n" + assessment.english_report)

        # Arabic Clinical Report Snippet
        print("\n--- ARABIC CLINICAL SUMMARY PREVIEW ---")
        ar_lines = assessment.arabic_report.splitlines()
        print("\n".join(ar_lines[:25]))
        print("...\n")

    print("=" * 80)
    print("  DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("=" * 80)

if __name__ == "__main__":
    main()
