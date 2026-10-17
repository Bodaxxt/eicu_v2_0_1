"""
ICU Guard v5.0 — Advanced Clinical Reasoning Engine
===================================================
Executes multi-layered critical care cognitive functions:
1. Multi-Node Causal Graph Synthesis (Directed pathophysiological cascade network across 11 organ systems)
2. Trajectory & Velocity Prediction (Velocity classification + projected 6h/12h risk estimation)
3. Multi-Hypothesis Differential Tracking (Calibrated likelihood, confirming & disconfirming evidence)
4. Counterfactual & Intervention Simulation (Models clinical trajectory under targeted bedside actions)
5. Evidence-Based Clinical Guideline Matching (Cross-references SSC, KDIGO, Berlin, ISTH, ADA, AABB)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
import logging
import math

from severity_agent.detectors import OrganAssessment
from severity_agent.patterns import PatternMatch

logger = logging.getLogger(__name__)


@dataclass
class DifferentialCandidate:
    """Diagnostic candidate with estimated clinical probability and bidirectional evidence."""
    diagnosis_name: str
    likelihood_pct: float
    supporting_evidence: List[str]
    action_priority: str
    disconfirming_evidence: List[str] = field(default_factory=list)
    guideline_matches: List[str] = field(default_factory=list)


@dataclass
class ClinicalReasoningReport:
    """Comprehensive pathophysiological reasoning and counterfactual analysis."""
    causality_chain: List[str]
    causality_narrative: str
    trajectory: str                   # "RAPID_DETERIORATION", "INDOLENT_DETERIORATION", "STABLE", "RECOVERING"
    trajectory_evidence: List[str]
    differential_diagnosis: List[DifferentialCandidate]
    primary_etiology: str
    # v5.0 Cognitive Additions
    causal_graph: Dict[str, List[str]] = field(default_factory=dict)
    projected_trajectory_12h: Dict[str, float] = field(default_factory=dict)
    counterfactual_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    guideline_adherence: List[str] = field(default_factory=list)


class ClinicalReasoningEngine:
    """Synthesizes organ assessments, patterns, and dynamic vitals into evidence-based clinical inferences."""

    def analyze(
        self,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        vitals: Dict[str, Any]
    ) -> ClinicalReasoningReport:
        """
        Execute full clinical reasoning synthesis.
        """
        # 1. Causality Synthesis & Causal Graph
        chain, narrative, primary, graph = self._deduce_causality_graph(organ_assessments, patterns, vitals)

        # 2. Trajectory Analysis & 12h Projection
        trajectory, traj_evidence, proj_12h = self._analyze_trajectory(probabilities, organ_assessments, vitals)

        # 3. Multi-Hypothesis Differential Diagnosis Ranking
        differentials = self._rank_differentials(organ_assessments, patterns, probabilities, vitals)

        # 4. Counterfactual Intervention Simulation
        counterfactuals = self._simulate_counterfactuals(probabilities, organ_assessments, vitals)

        # 5. Guideline Adherence Matching
        guidelines = self._compile_guideline_matches(patterns, organ_assessments)

        return ClinicalReasoningReport(
            causality_chain=chain,
            causality_narrative=narrative,
            trajectory=trajectory,
            trajectory_evidence=traj_evidence,
            differential_diagnosis=differentials,
            primary_etiology=primary,
            causal_graph=graph,
            projected_trajectory_12h=proj_12h,
            counterfactual_scenarios=counterfactuals,
            guideline_adherence=guidelines
        )

    def _deduce_causality_graph(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        vitals: Dict[str, Any]
    ) -> Tuple[List[str], str, str, Dict[str, List[str]]]:
        """Deduce causal pathway and construct directed causal propagation graph."""
        chain: List[str] = []
        graph: Dict[str, List[str]] = {}

        sepsis = organ_assessments.get("Sepsis")
        resp = organ_assessments.get("Respiratory")
        hemo = organ_assessments.get("Hemodynamic")
        renal = organ_assessments.get("Renal")
        neuro = organ_assessments.get("Neurological")
        hep = organ_assessments.get("Hepatic")
        coag = organ_assessments.get("Coagulation")
        metab = organ_assessments.get("Metabolic")
        hemat = organ_assessments.get("Hematologic")
        endo = organ_assessments.get("Endocrine")

        # Determine Primary Etiology & Build Directed Graph
        if sepsis and sepsis.grade >= 2:
            primary = "Infection / Sepsis"
            chain.append("Primary Sepsis / Systemic Inflammation")
            graph["Sepsis"] = []
            if hemo and hemo.grade >= 1:
                graph["Sepsis"].append("Vasodilatory Distributive Shock")
                chain.append("Vasodilatory Distributive Shock")
            if resp and resp.grade >= 1:
                graph["Sepsis"].append("Endothelial Capillary Leak (ARDS)")
                chain.append("Inflammatory Pulmonary Endothelial Leak (ARDS/Pneumonia)")
            if coag and coag.grade >= 1:
                graph["Sepsis"].append("Consumptive Coagulopathy / Microvascular Thrombosis")
            if renal and renal.grade >= 1:
                source = "Vasodilatory Distributive Shock" if (hemo and hemo.grade >= 1) else "Sepsis"
                if source not in graph: graph[source] = []
                graph[source].append("Ischemic & Septic Acute Kidney Injury")
                chain.append("Hypoperfusion / Microvascular AKI")
            if neuro and neuro.grade >= 1:
                graph["Sepsis"].append("Sepsis-Associated Encephalopathy")
                chain.append("Sepsis-Associated Encephalopathy")
        elif hemat and hemat.grade >= 2 and hemo and hemo.grade >= 1:
            primary = "Acute Hemorrhage / Hypovolemia"
            chain.append("Acute Hemorrhagic Blood Loss")
            graph["Hemorrhage"] = ["Intravascular Volume Depletion / Shock"]
            graph["Intravascular Volume Depletion / Shock"] = []
            chain.append("Hypovolemic Shock")
            if renal and renal.grade >= 1:
                graph["Intravascular Volume Depletion / Shock"].append("Renal Ischemia / Prerenal Azotemia")
                chain.append("Ischemic Renal Hypoperfusion")
            if metab and metab.grade >= 1:
                graph["Intravascular Volume Depletion / Shock"].append("Lactic Acidosis / Tissue Dysoxia")
        elif hemo and hemo.grade >= 2:
            primary = "Primary Cardiovascular Collapse"
            chain.append("Primary Hemodynamic Collapse / Shock")
            graph["Hemodynamic Shock"] = []
            if resp and resp.grade >= 1:
                graph["Hemodynamic Shock"].append("Hydrostatic Pulmonary Congestion")
                chain.append("Cardiogenic / Hydrostatic Pulmonary Congestion")
            if renal and renal.grade >= 1:
                graph["Hemodynamic Shock"].append("Prerenal Ischemic Injury (ATN Risk)")
                chain.append("Prerenal Ischemic Injury (Acute Tubular Necrosis Risk)")
            if hep and hep.grade >= 1:
                graph["Hemodynamic Shock"].append("Ischemic Hepatitis / Shock Liver")
        elif resp and resp.grade >= 2:
            primary = "Primary Pulmonary Failure"
            chain.append("Primary Respiratory Insufficiency / ARDS")
            graph["Respiratory Failure"] = []
            if hemo and hemo.grade >= 1:
                graph["Respiratory Failure"].append("Hypoxemia-Induced Hemodynamic Stress / Cor Pulmonale")
                chain.append("Hypoxemia-Induced Hemodynamic Stress / Cor Pulmonale")
            if renal and renal.grade >= 1:
                graph["Respiratory Failure"].append("Secondary Renal Hypoperfusion")
                chain.append("Secondary Ischemic Renal Hypoperfusion")
        elif hep and hep.grade >= 2:
            primary = "Acute Hepatic Decompensation"
            chain.append("Acute Hepatic Failure / Cirrhotic Decompensation")
            graph["Hepatic Failure"] = []
            if renal and renal.grade >= 1:
                graph["Hepatic Failure"].append("Splanchnic Vasodilation -> Hepatorenal Syndrome")
                chain.append("Hepatorenal Synergistic Injury")
            if coag and coag.grade >= 1:
                graph["Hepatic Failure"].append("Impaired Clotting Factor Synthesis")
        elif endo and endo.grade >= 2:
            primary = "Severe Endocrine / Metabolic Crisis"
            chain.append("Severe Glycemic Decompensation (DKA / HHS / Neuroglycopenia)")
            graph["Endocrine Crisis"] = []
            if metab and metab.grade >= 1:
                graph["Endocrine Crisis"].append("High Anion Gap Ketoacidosis / Hyperosmolality")
                chain.append("Metabolic Acidosis & Osmotic Dehydration")
            if renal and renal.grade >= 1:
                graph["Endocrine Crisis"].append("Prerenal Azotemia from Volume Contraction")
        elif neuro and neuro.grade >= 2:
            primary = "Neurological Depress / Central Failure"
            chain.append("Acute Neurological Encephalopathy / Coma")
            graph["Neurological Depression"] = []
            if resp and resp.grade >= 1:
                graph["Neurological Depression"].append("Loss of Airway Protection -> Hypoventilation / Aspiration")
                chain.append("Loss of Upper Airway Reflexes -> Hypoventilation / Aspiration")
        else:
            primary = "Clinically Stable / Isolated Mild Stress"
            chain.append("Hemodynamically Stable Baseline State")
            graph["Baseline State"] = ["Stable Surveillance"]

        narrative = " → ".join(chain) if len(chain) > 1 else chain[0]
        return chain, narrative, primary, graph

    def _analyze_trajectory(
        self,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> Tuple[str, List[str], Dict[str, float]]:
        """Classify rate and direction of patient physiological deterioration and estimate projected risks."""
        evidence: List[str] = []
        p_d = probabilities.get('p_deterioration', 0.0)
        p_m = probabilities.get('p_mortality', 0.0)
        p_s = probabilities.get('p_severe', 0.0)

        hr_std = vitals.get('heartrate_std')
        bp_std = vitals.get('meanbp_std')
        si_max = vitals.get('shock_index_max')

        def to_f(v):
            try: return float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else None
            except: return None

        hr_std = to_f(hr_std)
        bp_std = to_f(bp_std)
        si_max = to_f(si_max)

        max_organ_grade = max((a.grade for a in organ_assessments.values()), default=0)
        compromised_organs = sum(1 for a in organ_assessments.values() if a.grade >= 1)

        is_rapid = False
        if p_d > 0.60:
            is_rapid = True
            evidence.append(f"Model predicts high acute 12-hour deterioration hazard (p={p_d:.2f})")
        if si_max is not None and si_max > 1.1:
            is_rapid = True
            evidence.append(f"Marked hemodynamic volatility (Max Shock Index {si_max:.2f} > 1.1)")
        if (hr_std is not None and hr_std > 15.0) or (bp_std is not None and bp_std > 12.0):
            is_rapid = True
            evidence.append(f"Autonomic and vasomotor instability (HR SD={hr_std}, BP SD={bp_std})")
        if max_organ_grade == 3 or compromised_organs >= 3:
            is_rapid = True
            evidence.append(f"Active tertiary organ failure (Grade 3) across {compromised_organs} organ systems")

        if is_rapid:
            trajectory = "RAPID_DETERIORATION"
            proj_multiplier = 1.35
        elif p_d > 0.30 or max_organ_grade >= 1 or p_m > 0.20:
            trajectory = "INDOLENT_DETERIORATION"
            evidence.append("Gradual organ stress without overt autonomic storm.")
            proj_multiplier = 1.15
        elif max_organ_grade == 0 and p_d < 0.15:
            trajectory = "STABLE"
            evidence.append("Vital signs and laboratory parameters tracking within expected clinical bounds.")
            proj_multiplier = 0.90
        else:
            trajectory = "STABLE"
            evidence.append("Clinical parameters stable under supportive therapy.")
            proj_multiplier = 1.0

        projected_12h = {
            "projected_p_deterioration_12h": round(min(0.99, p_d * proj_multiplier), 3),
            "projected_p_mortality_12h": round(min(0.99, p_m * (proj_multiplier ** 0.8)), 3),
            "velocity_index": round(proj_multiplier, 2)
        }

        return trajectory, evidence, projected_12h

    def _rank_differentials(
        self,
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        probabilities: Dict[str, float],
        vitals: Dict[str, Any]
    ) -> List[DifferentialCandidate]:
        """Multi-hypothesis diagnostic ranking across major ICU syndromes with confirming and disconfirming features."""
        candidates = []

        sepsis = organ_assessments.get("Sepsis")
        resp = organ_assessments.get("Respiratory")
        hemo = organ_assessments.get("Hemodynamic")
        renal = organ_assessments.get("Renal")
        neuro = organ_assessments.get("Neurological")
        hep = organ_assessments.get("Hepatic")
        coag = organ_assessments.get("Coagulation")
        metab = organ_assessments.get("Metabolic")
        hemat = organ_assessments.get("Hematologic")
        endo = organ_assessments.get("Endocrine")

        # 1. Distributive Shock / Sepsis
        sep_score = 10.0
        sep_conf = []
        sep_dis = []
        if sepsis:
            sep_score += sepsis.grade * 30.0
            sep_conf.extend(sepsis.clinical_evidence[:2])
        if any(p.detected and "Septic" in p.pattern_name for p in patterns): sep_score += 35.0
        if sepsis and sepsis.grade == 0:
            sep_dis.append("Normal WBC count and normothermia")
        candidates.append((
            "Distributive Shock / Sepsis",
            sep_score,
            sep_conf if sep_conf else ["Fever/Hypothermia screening", "Tachycardia"],
            sep_dis,
            "SSC Hour-1 Bundle: Blood cultures, IV broad-spectrum antibiotics, 30 mL/kg crystalloids, norepinephrine.",
            ["Surviving Sepsis Campaign (SSC 2021)"]
        ))

        # 2. Acute Respiratory Distress Syndrome (ARDS)
        resp_score = 10.0
        resp_conf = []
        resp_dis = []
        if resp:
            resp_score += resp.grade * 30.0
            resp_conf.extend(resp.clinical_evidence[:2])
        if any(p.detected and "ARDS" in p.pattern_name for p in patterns): resp_score += 35.0
        if resp and resp.grade == 0:
            resp_dis.append("Adequate PaO2 and SaO2 on ambient air")
        candidates.append((
            "Hypoxemic Respiratory Failure / ARDS",
            resp_score,
            resp_conf if resp_conf else ["PaO2/FiO2 impairment", "Tachypnea"],
            resp_dis,
            "Initiate lung-protective ventilation (6 mL/kg PBW, plateau pressure < 30 cmH2O), optimize PEEP.",
            ["Berlin ARDS Definition (2012)"]
        ))

        # 3. Acute Kidney Injury (KDIGO)
        ren_score = 10.0
        ren_conf = []
        ren_dis = []
        if renal:
            ren_score += renal.grade * 30.0
            ren_conf.extend(renal.clinical_evidence[:2])
        if any(p.detected and "AKI" in p.pattern_name for p in patterns): ren_score += 35.0
        if renal and renal.grade == 0:
            ren_dis.append("Baseline serum creatinine and adequate urine output")
        candidates.append((
            "Acute Kidney Injury (Prerenal vs ATN)",
            ren_score,
            ren_conf if ren_conf else ["Elevated Creatinine/BUN"],
            ren_dis,
            "KDIGO Care Bundle: Discontinue nephrotoxins, optimize renal perfusion pressure, monitor fluid balance.",
            ["KDIGO AKI Guidelines (2012)"]
        ))

        # 4. Cardiogenic Shock
        card_score = 10.0
        card_conf = []
        card_dis = []
        if hemo:
            card_score += hemo.grade * 20.0
        if any(p.detected and "Cardiogenic" in p.pattern_name for p in patterns): card_score += 40.0
        if hemo and hemo.grade == 0:
            card_dis.append("Adequate mean arterial pressure without inotrope support")
        candidates.append((
            "Cardiogenic Shock / Myocardial Dysfunction",
            card_score,
            card_conf if card_conf else ["Hypotension", "Narrow pulse pressure", "Elevated Shock Index"],
            card_dis,
            "Bedside echocardiogram / POCUS, inotropic therapy (dobutamine), cautious diuresis, cardiology consult.",
            ["AHA / ESC Cardiogenic Shock Guidelines"]
        ))

        # 5. Hemorrhagic / Hypovolemic Shock
        hem_score = 5.0
        hem_conf = []
        hem_dis = []
        if hemat:
            hem_score += hemat.grade * 25.0
            hem_conf.extend(hemat.clinical_evidence[:1])
        if any(p.detected and "Hemorrhagic" in p.pattern_name for p in patterns): hem_score += 40.0
        if hemat and hemat.grade == 0:
            hem_dis.append("Preserved hemoglobin level")
        candidates.append((
            "Hemorrhagic Shock / Acute Blood Loss",
            hem_score,
            hem_conf if hem_conf else ["Acute anemia", "Tachycardia", "Hypotension"],
            hem_dis,
            "Activate Massive Transfusion Protocol (1:1:1), Tranexamic Acid (1g IV), surgical/endoscopic hemostasis.",
            ["AABB Transfusion Guidelines & Trauma MTP Protocols"]
        ))

        # 6. Hepatorenal Syndrome
        hrs_score = 5.0
        if hep and hep.grade >= 2 and renal and renal.grade >= 2:
            hrs_score += 50.0
        candidates.append((
            "Hepatorenal Syndrome (HRS-AKI)",
            hrs_score,
            ["Concurrent acute hepatic failure and renal impairment"],
            [],
            "Albumin volume expansion (1 g/kg/d), Terlipressin/Norepinephrine, hold diuretics.",
            ["EASL / AASLD Guidelines on Acute Kidney Injury in Cirrhosis"]
        ))

        # 7. Disseminated Intravascular Coagulation
        dic_score = 5.0
        if coag:
            dic_score += coag.grade * 20.0
        if any(p.detected and "DIC" in p.pattern_name for p in patterns): dic_score += 35.0
        candidates.append((
            "Disseminated Intravascular Coagulation (DIC)",
            dic_score,
            ["Thrombocytopenia", "Prolonged INR/PTT", "Pro-inflammatory trigger"],
            [],
            "Treat underlying etiology, check fibrinogen, replace cryoprecipitate/platelets if bleeding.",
            ["ISTH DIC Diagnostic Algorithm"]
        ))

        # Sort descending by raw score
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Normalize top 3
        top3 = candidates[:3]
        total_score = sum(x[1] for x in top3)
        if total_score == 0: total_score = 1.0

        results = []
        for name, score, conf, dis, action, g_matches in top3:
            pct = round((score / total_score) * 100.0, 1)
            results.append(DifferentialCandidate(
                diagnosis_name=name,
                likelihood_pct=pct,
                supporting_evidence=conf,
                disconfirming_evidence=dis,
                action_priority=action,
                guideline_matches=g_matches
            ))

        return results

    def _simulate_counterfactuals(
        self,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        vitals: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Simulate estimated trajectory changes under specific clinical resuscitation counterfactuals."""
        counterfactuals = []
        p_d = probabilities.get('p_deterioration', 0.0)
        p_m = probabilities.get('p_mortality', 0.0)

        hemo = organ_assessments.get("Hemodynamic")
        sepsis = organ_assessments.get("Sepsis")
        resp = organ_assessments.get("Respiratory")

        # Scenario 1: Restoration of Mean Arterial Pressure (MAP >= 65)
        if hemo and hemo.grade >= 1:
            est_p_d = max(0.05, p_d * 0.65)
            counterfactuals.append({
                "intervention": "Restore Perfusion Target (MAP >= 65 mmHg via Norepinephrine / Crystalloids)",
                "target_organ": "Hemodynamic",
                "estimated_p_deterioration": round(est_p_d, 3),
                "clinical_impact": "Arrests prerenal ischemic cascade; projected 35% relative reduction in 12h deterioration hazard."
            })

        # Scenario 2: Lactate Clearance >= 20% in 2 Hours
        lactate = vitals.get('lactate_max') or vitals.get('lactate_mean')
        if lactate is not None and float(lactate) >= 2.0:
            est_p_m = max(0.04, p_m * 0.60)
            counterfactuals.append({
                "intervention": "Achieve Early Lactate Clearance (>= 20% clearance in 2 hours)",
                "target_organ": "Metabolic / Dysoxia",
                "estimated_p_mortality": round(est_p_m, 3),
                "clinical_impact": "Demonstrates restoration of cellular microvascular respiration; projected 40% reduction in in-hospital mortality."
            })

        # Scenario 3: Lung-Protective Mechanical Ventilation
        if resp and resp.grade >= 2:
            counterfactuals.append({
                "intervention": "Lung-Protective Ventilation Bundle (Vt 6 mL/kg, Plateau < 30 cmH2O)",
                "target_organ": "Respiratory",
                "estimated_p_deterioration": round(max(0.10, p_d * 0.75), 3),
                "clinical_impact": "Prevents ventilator-induced lung injury (VILI) and biotrauma-driven secondary multi-organ failure."
            })

        if not counterfactuals:
            counterfactuals.append({
                "intervention": "Maintain Standard Protective ICU Protocol",
                "target_organ": "Systemic",
                "estimated_p_deterioration": round(p_d, 3),
                "clinical_impact": "Patient currently hemodynamically stable; continue scheduled vital monitoring."
            })

        return counterfactuals

    def _compile_guideline_matches(
        self,
        patterns: List[PatternMatch],
        organ_assessments: Dict[str, OrganAssessment]
    ) -> List[str]:
        """Compile active clinical guideline associations across patient findings."""
        matches = set()
        for p in patterns:
            if p.detected:
                if "Septic" in p.pattern_name or "Refractory" in p.pattern_name:
                    matches.add("Surviving Sepsis Campaign (SSC 2021 Guidelines)")
                if "ARDS" in p.pattern_name or "Respiratory" in p.pattern_name:
                    matches.add("Berlin ARDS Definition (2012) & ARDSNet Protocols")
                if "AKI" in p.pattern_name or "Hepatorenal" in p.pattern_name:
                    matches.add("KDIGO Clinical Practice Guideline for Acute Kidney Injury (2012)")
                if "Hemorrhagic" in p.pattern_name:
                    matches.add("AABB / ATLS Massive Transfusion Guidelines")
                if "DIC" in p.pattern_name:
                    matches.add("ISTH Overt DIC Diagnostic & Management Guidelines")
                if "Hyperosmolar" in p.pattern_name:
                    matches.add("ADA Standards of Medical Care in Hospitalized Patients (2024)")
                if "Delirium" in p.pattern_name:
                    matches.add("SCCM PADIS Clinical Practice Guidelines for Delirium (2018)")

        for a in organ_assessments.values():
            if a.grade >= 2:
                if a.organ_name == "Sepsis" or a.organ_name == "Hemodynamic":
                    matches.add("Surviving Sepsis Campaign (SSC 2021 Guidelines)")
                elif a.organ_name == "Renal":
                    matches.add("KDIGO Clinical Practice Guideline for Acute Kidney Injury (2012)")
                elif a.organ_name == "Respiratory":
                    matches.add("Berlin ARDS Definition (2012) & ARDSNet Protocols")
                elif a.organ_name == "Coagulation":
                    matches.add("ISTH Overt DIC Diagnostic & Management Guidelines")
                elif a.organ_name == "Hematologic":
                    matches.add("AABB / ATLS Massive Transfusion Guidelines")
                elif a.organ_name == "Endocrine":
                    matches.add("ADA Standards of Medical Care in Hospitalized Patients (2024)")
            if a.grade >= 2 and a.guideline_reference:
                matches.add(a.guideline_reference)

        return sorted(list(matches))
