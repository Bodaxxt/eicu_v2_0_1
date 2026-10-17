# 🩺 ICU Guard v5.0 — Clinical Rationale & Evidence Base

**Medical Guidelines, Physiological Thresholds, and Evidence Justifications**  
*Document Version: 5.0.0 | Clinical Lead Reference Guide*

---

## 1. Overview & Regulatory Medical Context

ICU Guard v5.0 avoids arbitrary mathematical cutoffs. Every numerical threshold, injury grade, syndrome definition, and escalation rule is grounded directly in peer-reviewed clinical practice guidelines endorsed by international critical care societies:
- **Surviving Sepsis Campaign (SSC 2021 Guidelines)**
- **Kidney Disease: Improving Global Outcomes (KDIGO 2012 Clinical Practice Guideline for AKI)**
- **Berlin Definition of Acute Respiratory Distress Syndrome (ARDS 2012)**
- **International Society on Thrombosis and Haemostasis (ISTH) Overt DIC Algorithm**
- **American Diabetes Association (ADA 2024 Standards of Medical Care in Hospitalized Patients)**
- **Association for the Advancement of Blood & Biotherapies (AABB 2023 Transfusion Guidelines)**
- **Society of Critical Care Medicine (SCCM 2018 PADIS Guidelines for Delirium)**
- **Stewart Physicochemical Acid-Base Approach & Arterial Blood Gas Protocols**
- **Sequential Organ Failure Assessment (SOFA 2016 / Sepsis-3 Consensus)**

---

## 2. Absolute Red Flag Thresholds

When any single absolute red flag is breached, **immediate escalation to TIER 1 (CRITICAL)** occurs regardless of ML probabilities:

| Parameter | Threshold | Physiological & Medical Justification |
| :--- | :--- | :--- |
| **`meanbp_min`** | $< 50\text{ mmHg}$ | Autoregulatory threshold for cerebral and coronary perfusion. Mean arterial pressure below 50 mmHg results in profound ischemic microvascular hypoperfusion and irreversible cellular injury. |
| **`sbp_min`** | $< 70\text{ mmHg}$ | Overt cardiovascular collapse; severe cardiogenic or vasodilatory shock failing compensatory mechanisms. |
| **`sao2_min`** | $< 50\%$ | Extreme arterial anoxia; imminent hypoxic cardiac arrest and rapid brain tissue hypoxia. |
| **`pao2_min`** | $< 50\text{ mmHg}$ | Severe refractory hypoxemic gas exchange failure under supplemental oxygen. Berlin definition severe tier. |
| **`lactate_max`** | $> 8.0\text{ mmol/L}$ | Severe lactic dysoxia; indicative of extensive systemic tissue hypoperfusion, mitochondrial dysfunction, and $>50\%$ ICU mortality risk. |
| **`ph_min`** | $< 7.10$ | Critical acidemia; profound depression of myocardial contractility, severe blunting of catecholamine responsiveness, and life-threatening ventricular arrhythmias. |
| **`gcs_min`** | $< 8.0$ | Severe coma; loss of protective airway reflexes (cough, gag) with extreme risk of fatal pulmonary aspiration. Indication for immediate endotracheal intubation. |
| **`glucose_min`** | $< 40\text{ mg/dL}$ | Critical neuroglycopenia; rapid development of seizures, coma, and irreversible ischemic neuronal death if not immediately corrected with IV dextrose. |
| **`platelets_min`** | $< 20\times 10^9\text{/L}$ | Critical spontaneous hemorrhage hazard; high risk of fatal intracranial or gastrointestinal bleeding. Urgent trigger for prophylactic platelet transfusion. |
| **`potassium_max`** | $> 6.5\text{ mmol/L}$ | Severe hyperkalemia; progressive QRS widening, sine wave formation, and imminent ventricular fibrillation / asystolic cardiac arrest. |
| **`potassium_min`** | $< 2.5\text{ mmol/L}$ | Severe hypokalemia; delayed myocardial repolarization, prominent U-waves, and life-threatening Torsades de Pointes. |

---

## 3. Organ Detector Evidence Base & Thresholds (11 Systems)

### 1. Respiratory System (`RespiratoryDetector`)
*Guideline Reference: Berlin ARDS Definition (2012) & Hypoxemia Protocols*
- **Grade 3 (Severe / Failure):**
  - $SaO2 < 85\%$ or $PaO2 < 55\text{ mmHg}$ (severe gas exchange failure)
  - $RR \ge 35\text{ /min}$ (impending respiratory muscle exhaustion)
  - $RR < 8\text{ /min}$ (central respiratory depression / impending apnea)
- **Grade 2 (Moderate ARDS):**
  - $SaO2 < 90\%$ or $PaO2 < 65\text{ mmHg}$
  - $RR \ge 28\text{ /min}$ (tachypneic compensatory work of breathing)
  - $O2\text{ Reserve} < 50$
- **Grade 1 (Mild Respiratory Stress):**
  - $SaO2 < 93\%$ or $PaO2 < 80\text{ mmHg}$ or $RR \ge 22\text{ /min}$
- **Grade 0 (Normal):** $SaO2 \ge 93\%$, $PaO2 \ge 80\text{ mmHg}$, $RR \in [8, 22]$.

### 2. Hemodynamic System (`HemodynamicDetector`)
*Guideline Reference: Surviving Sepsis Campaign (SSC 2021) & Shock Index Protocols*
- **Grade 3 (Severe / Uncompensated Shock):**
  - $MAP < 55\text{ mmHg}$ or $SBP < 75\text{ mmHg}$
  - $\text{Shock Index } (SI) > 1.3$ (critical uncompensated hypovolemia/pump failure)
  - $HR \ge 140\text{ bpm}$ or $HR < 40\text{ bpm}$ (severe bradycardia / impending arrest)
- **Grade 2 (Moderate Shock / Perfusion Target Failure / Hypertensive Crisis):**
  - $MAP < 65\text{ mmHg}$ (unmet SSC target for tissue perfusion)
  - $SBP < 90\text{ mmHg}$ or $SI > 0.9$ or $HR \ge 115\text{ bpm}$
  - $SBP \ge 180\text{ mmHg}$ (Hypertensive urgency/crisis with acute afterload elevation)
- **Grade 1 (Mild Vasomotor Stress):**
  - $MAP < 70\text{ mmHg}$ or $SBP < 100\text{ mmHg}$ or $SI > 0.7$ or $HR \ge 100\text{ bpm}$
- **Grade 0 (Normal):** $MAP \ge 70\text{ mmHg}$, $SBP \ge 100\text{ mmHg}$, $HR \in [50, 100]$, $SI \le 0.7$.

### 3. Renal System (`RenalDetector`)
*Guideline Reference: KDIGO Clinical Practice Guideline for Acute Kidney Injury (2012)*
- **Grade 3 (KDIGO Stage 3 / Severe AKI):**
  - Serum Creatinine $\ge 4.0\text{ mg/dL}$ (or $\ge 3\times$ baseline)
  - $BUN \ge 80\text{ mg/dL}$
  - Urine output $< 0.3\text{ mL/kg/h}$ for $\ge 24\text{ hours}$ or anuria for $\ge 12\text{ hours}$
- **Grade 2 (KDIGO Stage 2 / Moderate AKI):**
  - Serum Creatinine $\ge 2.0\text{ mg/dL}$ (or $2.0-2.9\times$ baseline)
  - $BUN \ge 50\text{ mg/dL}$
  - Urine output $< 0.5\text{ mL/kg/h}$ for $\ge 12\text{ hours}$
- **Grade 1 (KDIGO Stage 1 / Early AKI):**
  - Serum Creatinine $\ge 1.3\text{ mg/dL}$
  - $BUN \ge 30\text{ mg/dL}$
  - Urine output $< 0.5\text{ mL/kg/h}$ for $\ge 6\text{ hours}$
- **Grade 0 (Normal):** Serum Creatinine $< 1.3\text{ mg/dL}$, $BUN < 30\text{ mg/dL}$.

### 4. Neurological System (`NeurologicalDetector`)
*Guideline Reference: Glasgow Coma Scale (GCS) & Neurocritical Care Airway Guidelines*
- **Grade 3 (Severe Impairment / Coma):**
  - $GCS \le 8$ (indication for immediate endotracheal intubation)
- **Grade 2 (Moderate Impairment / Stupor):**
  - $GCS \in [9, 12]$ (significant cognitive depression, loss of verbal orientation)
- **Grade 1 (Mild Neurological Stress / Lethargy):**
  - $GCS \in [13, 14]$
- **Grade 0 (Normal / Alert):** $GCS = 15$.

### 5. Sepsis Subsystem (`SepsisDetector`)
*Guideline Reference: Sepsis-3 Consensus & Surviving Sepsis Campaign (2021)*
- Evaluates 4 SIRS criteria:
  - Temperature $> 38.3^\circ\text{C}$ or $< 36.0^\circ\text{C}$
  - Heart Rate $> 90\text{ bpm}$
  - Respiratory Rate $> 20\text{ /min}$
  - WBC $> 12.0\times 10^3\text{/\mu L}$ or $< 4.0\times 10^3\text{/\mu L}$
- **Grade 3 (Severe Sepsis with Dysoxia):** $\text{SIRS} \ge 2$ plus Serum Lactate $\ge 4.0\text{ mmol/L}$ (cellular dysoxia).
- **Grade 2 (High SIRS Burden / Sepsis):** $\text{SIRS} \ge 3$ or ($\text{SIRS} \ge 2$ with Lactate $\ge 2.2\text{ mmol/L}$).
- **Grade 1 (SIRS Present):** $\text{SIRS} \ge 2$.
- **Grade 0 (No Sepsis):** $\text{SIRS} < 2$, Lactate $< 2.0\text{ mmol/L}$.

### 6. Hepatic System (`HepaticDetector`)
*Guideline Reference: SOFA Liver Criteria & EASL / AASLD Guidelines*
- **Grade 3 (Severe Hepatic Failure / Decompensation):**
  - Total Bilirubin $\ge 6.0\text{ mg/dL}$ (SOFA Liver 3-4) or $INR \ge 2.5$
- **Grade 2 (Moderate Hepatic Dysfunction):**
  - Total Bilirubin $\ge 2.0\text{ mg/dL}$ (SOFA Liver 2) or $INR \ge 1.7$
- **Grade 1 (Mild Hepatic Stress / Cholestasis):**
  - Total Bilirubin $\ge 1.2\text{ mg/dL}$ or $INR \ge 1.3$
- **Grade 0 (Normal):** Total Bilirubin $< 1.2\text{ mg/dL}$, $INR < 1.3$.

### 7. Coagulation System (`CoagulationDetector`)
*Guideline Reference: ISTH Overt DIC Scoring Guidelines & SOFA Coagulation Criteria*
- **Grade 3 (Severe Coagulopathy / Critical Bleeding Risk):**
  - Platelets $< 50\times 10^9\text{/L}$ (SOFA Coag 3) or $INR \ge 2.2$ or $PTT \ge 60\text{ s}$
- **Grade 2 (Moderate Coagulopathy / Consumptive Risk):**
  - Platelets $< 100\times 10^9\text{/L}$ (SOFA Coag 2) or $INR \ge 1.6$ or $PTT \ge 45\text{ s}$
- **Grade 1 (Mild Coagulation Stress):**
  - Platelets $< 150\times 10^9\text{/L}$ or $INR \ge 1.3$
- **Grade 0 (Normal Hemostasis):** Platelets $\ge 150\times 10^9\text{/L}$, $INR < 1.3$, $PTT < 38\text{ s}$.

### 8. Metabolic System (`MetabolicDetector`)
*Guideline Reference: Stewart Physicochemical Acid-Base Approach & ABG Critical Care Protocols*
- **Grade 3 (Severe Life-Threatening Acidemia / Severe Dysoxia):**
  - Arterial $pH < 7.15$ or Serum Lactate $\ge 6.0\text{ mmol/L}$
- **Grade 2 (Moderate Acidemia / Severe Alkalemia):**
  - Arterial $pH < 7.25$ or Arterial $pH > 7.55$ (severe metabolic/respiratory alkalemia) or Serum Lactate $\ge 4.0\text{ mmol/L}$
- **Grade 1 (Mild Acid-Base Disruption):**
  - Arterial $pH < 7.35$ or $pH > 7.48$ or Serum Lactate $\ge 2.2\text{ mmol/L}$
- **Grade 0 (Normal Acid-Base Homeostasis):** $pH \in [7.35, 7.45]$, Lactate $< 2.0\text{ mmol/L}$.

### 9. Endocrine System (`EndocrineDetector`)
*Guideline Reference: ADA Standards of Medical Care in Hospitalized Patients (2024)*
- **Grade 3 (Critical Endocrine Emergency):**
  - Blood Glucose $< 50\text{ mg/dL}$ (severe neuroglycopenia) or Blood Glucose $\ge 500\text{ mg/dL}$ (hyperosmolar hyperglycemic state)
- **Grade 2 (Severe Hypoglycemia / Significant Hyperglycemia):**
  - Blood Glucose $< 70\text{ mg/dL}$ (hypoglycemia threshold) or Blood Glucose $\ge 300\text{ mg/dL}$
- **Grade 1 (Mild Dysglycemia):**
  - Blood Glucose $\ge 180\text{ mg/dL}$ (ICU target ceiling)
- **Grade 0 (Euglycemia):** Blood Glucose $\in [70, 180]\text{ mg/dL}$.

### 10. Hematologic System (`HematologicDetector`)
*Guideline Reference: AABB Restrictive Transfusion Guidelines (2023)*
- **Grade 3 (Severe Anemia / Critical Transfusion Trigger):**
  - Hemoglobin $< 7.0\text{ g/dL}$ (universal guideline trigger for packed RBC transfusion in non-bleeding ICU patients)
- **Grade 2 (Moderate Anemia):**
  - Hemoglobin $< 8.5\text{ g/dL}$ (transfusion threshold in acute coronary syndrome or symptomatic shock)
- **Grade 1 (Mild Anemia):**
  - Hemoglobin $< 10.0\text{ g/dL}$
- **Grade 0 (Normal):** Hemoglobin $\ge 10.0\text{ g/dL}$.

### 11. Nutritional System (`NutritionalDetector`)
*Guideline Reference: ESPEN Guidelines on Clinical Nutrition in the Intensive Care Unit*
- **Grade 3 (Critical Cachexia / Severe Hypoalbuminemia):**
  - $BMI < 16.0\text{ kg/m}^2$ (severe protein-calorie malnutrition) or Serum Albumin $< 2.0\text{ g/dL}$ (severe loss of oncotic pressure and capillary leak marker)
- **Grade 2 (Moderate Nutritional Risk / Morbid Obesity):**
  - $BMI < 18.5\text{ kg/m}^2$ or $BMI \ge 40.0\text{ kg/m}^2$ (morbid obesity requiring specialized mechanical ventilation mechanics) or Serum Albumin $< 2.8\text{ g/dL}$
- **Grade 1 (Mild Nutritional Risk):**
  - $BMI \ge 30.0\text{ kg/m}^2$ or Serum Albumin $< 3.5\text{ g/dL}$
- **Grade 0 (Adequate Reserves):** $BMI \in [18.5, 29.9]\text{ kg/m}^2$, Serum Albumin $\ge 3.5\text{ g/dL}$.

---

## 4. Clinical Syndrome Patterns (16 Syndromes)

| Syndrome Pattern | Diagnostic Criteria Met | Urgency Tier | Clinical Directive |
| :--- | :--- | :--- | :--- |
| **Septic Shock** | Sepsis $\ge 2$ + Hemodynamic $\ge 1$ + Lactate $\ge 4.0\text{ mmol/L}$ | `IMMEDIATE` | Surviving Sepsis Hour-1 Bundle: Blood cultures, IV broad-spectrum antibiotics, $30\text{ mL/kg}$ crystalloids, norepinephrine titration for $MAP \ge 65$. |
| **ARDS** | Resp $\ge 2$ + $PaO2 < 60\text{ mmHg}$ ($SaO2 < 88\%$) | `IMMEDIATE` | ARDSNet lung-protective ventilation: $V_t = 4-6\text{ mL/kg}$ PBW, plateau pressure $< 30\text{ cmH2O}$, PEEP titration. |
| **AKI** | Renal $\ge 2$ or (Renal $\ge 1$ + Sepsis/Shock) | `URGENT` | KDIGO bundle: Stop nephrotoxics, optimize renal perfusion pressure, hourly Foley monitoring. |
| **MOF / MODS** | $\ge 3$ organ systems with Grade $\ge 2$ | `IMMEDIATE` | Emergency intensivist bedside review, multi-organ support, invasive line placement. |
| **Neuro-Respiratory** | Neuro $\ge 2$ ($GCS \le 12$) + Resp $\ge 2$ | `URGENT` | Loss of airway reflexes; elevate head of bed 30°, prepare for endotracheal intubation. |
| **Cardiogenic Shock** | Hemodynamic $\ge 1$ + $SI \ge 0.9$ + Troponin or Pulmonary Congestion | `URGENT` | Bedside POCUS echocardiography, inotropic support (dobutamine/milrinone), cautious fluid challenge. |
| **Hemorrhagic Shock** | Hemodynamic $\ge 1$ + Hematologic $\ge 2$ ($Hb < 8.5$) + $SI \ge 1.0$ | `IMMEDIATE` | Activate Massive Transfusion Protocol (1:1:1 PRBC:FFP:Platelets), IV Tranexamic Acid (1g), surgical hemostasis. |
| **DIC** | Coagulation $\ge 2$ + Sepsis/Shock | `URGENT` | Treat trigger, check fibrinogen, replace cryoprecipitate/platelets if bleeding. |
| **ICU Delirium** | Neuro $\ge 1$ ($GCS \in [9, 13]$) + Sepsis/Metabolic | `MONITOR` | SCCM PADIS ABCDEF bundle: Reorientation, sleep hygiene, avoid benzodiazepines, CAM-ICU screening. |
| **Refractory Shock** | Hemodynamic $\ge 2$ + Lactate $\ge 4.0$ failing fluids | `URGENT` | Add second-line vasopressor (vasopressin $0.03\text{ U/min}$), hydrocortisone, arterial line. |
| **Type 1 Resp Failure** | Resp $\ge 2$ + $PaO2 < 60\text{ mmHg}$, $SaO2 < 88\%$ | `IMMEDIATE` | High-Flow Nasal Cannula (HFNC) with ROX index monitoring; prepare lung-protective ventilation. |
| **Type 2 Resp Failure** | Resp $\ge 2$ + $pH < 7.25$ without severe lactic acid | `IMMEDIATE` | Non-invasive positive pressure ventilation (BiPAP) if alert, or urgent invasive intubation. |
| **Hepatorenal Syndrome** | Hepatic $\ge 2$ + Renal $\ge 2$ | `IMMEDIATE` | Discontinue diuretics; IV Albumin ($1\text{ g/kg}$, max $100\text{g/d}$); Terlipressin/Norepinephrine. |
| **Post-Op Deterioration** | PACU/Surgical admission + Hemodynamic $\ge 2$ | `URGENT` | Screen for occult internal hemorrhage, anastomosis leak, or opioid hypoventilation. |
| **Severe Acidemia** | Metabolic $\ge 2$ + $pH < 7.20$ | `IMMEDIATE` | Alveolar ventilation to eliminate CO2, optimize tissue perfusion, consider CVVHDF buffer therapy. |
| **Hyperosmolar Crisis** | Endocrine $\ge 2$ ($Glucose \ge 350$) + $pH < 7.30$ | `URGENT` | IV regular insulin infusion ($0.1\text{ U/kg/h}$), isotonic saline volume repletion, potassium monitoring. |

---

## 5. Summary of Clinical Safety Governance

1. **Deterministic Execution:** Eliminates random hallucinations or drift from black-box models.
2. **Exhaustive Red Flag Coverage:** 11 vital and laboratory red flags guarantee patients with imminent life threats are never triaged into low-acuity categories.
3. **Auditability:** Complete backward traceability to established medical literature ensures regulatory compliance under FDA SaMD (Software as a Medical Device) and EU MDR Class IIb frameworks.

---
*ICU Guard v5.0 — Medical Excellence, Rigorous Validation, Zero Compromise.*
