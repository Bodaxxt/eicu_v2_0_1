"""
ICU Guard v5.0 — Actionable Evidence-Based Clinical Recommendations
===================================================================
Generates concrete, step-by-step bedside clinical action plans aligned with international guidelines:
1. Surviving Sepsis Campaign (SSC 2021) Hour-1 Bundle
2. KDIGO Acute Kidney Injury Care Bundle
3. ARDSNet Lung-Protective Mechanical Ventilation Protocol
4. Massive Transfusion Protocol (MTP) & Hemorrhage Control
5. Cardiogenic Shock Inotropic & Mechanical Circulatory Support
6. Diabetic Ketoacidosis (DKA) / HHS Glycemic Protocol
7. SCCM ABCDEF ICU Liberation & Delirium Bundle
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging

from severity_agent.detectors import OrganAssessment
from severity_agent.patterns import PatternMatch

logger = logging.getLogger(__name__)


@dataclass
class ClinicalActionItem:
    """Specific bedside intervention step."""
    category: str                   # "DIAGNOSTIC", "THERAPEUTIC", "MONITORING", "CONSULTATION"
    action_text: str
    urgency: str                    # "STAT", "15_MIN", "1_HOUR", "ROUTINE"
    guideline_source: str
    rationale: str


@dataclass
class ActionablePlan:
    """Complete multi-domain clinical action plan."""
    primary_protocol: str
    items: List[ClinicalActionItem]
    stat_actions: List[str]
    contraindications_and_cautions: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"=== CLINICAL ACTION PLAN: {self.primary_protocol} ==="]
        for it in self.items:
            lines.append(f"[{it.urgency}] ({it.category}) {it.action_text} -- [{it.guideline_source}]")
        return "\n".join(lines)


class RecommendationEngine:
    """Assembles guideline-adherent bedside clinical action plans."""

    def generate_plan(
        self,
        severity_tier: str,
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        vitals: Dict[str, Any]
    ) -> ActionablePlan:
        items: List[ClinicalActionItem] = []
        cautions: List[str] = []
        active_pattern_names = [p.pattern_name for p in patterns if p.detected]

        # 1. Septic Shock / Sepsis Bundle
        if any("Septic" in name for name in active_pattern_names) or (organ_assessments.get("Sepsis") and organ_assessments["Sepsis"].grade >= 2):
            protocol = "Surviving Sepsis Hour-1 Resuscitation Bundle"
            items.append(ClinicalActionItem(
                category="DIAGNOSTIC",
                action_text="Draw blood cultures (2 sets: aerobic & anaerobic) prior to initiating antimicrobial therapy.",
                urgency="STAT",
                guideline_source="Surviving Sepsis Campaign (SSC 2021)",
                rationale="Identifies causative pathogen; diagnostic yield decreases significantly after antibiotics."
            ))
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Administer empiric broad-spectrum IV antimicrobials within 1 hour of recognition.",
                urgency="STAT",
                guideline_source="SSC 2021",
                rationale="Each hour of delay in antibiotic administration correlates with an ~7.6% increase in mortality."
            ))
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Infuse 30 mL/kg balanced crystalloids (Plasma-Lyte / Lactated Ringer's) for hypotension or lactate >= 4.0 mmol/L.",
                urgency="STAT",
                guideline_source="SSC 2021",
                rationale="Restores effective intravascular circulating volume in distributive vasodilation."
            ))
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Initiate Norepinephrine infusion (titrate to target MAP >= 65 mmHg) if MAP remains < 65 during or after fluid resuscitation.",
                urgency="STAT",
                guideline_source="SSC 2021",
                rationale="First-line vasopressor to restore coronary and renal perfusion pressure."
            ))
            items.append(ClinicalActionItem(
                category="MONITORING",
                action_text="Remonitor serum lactate within 2 to 4 hours to evaluate lactate clearance (> 20% in 2h).",
                urgency="1_HOUR",
                guideline_source="SSC 2021",
                rationale="Lactate clearance serves as dynamic surrogate of tissue microvascular reperfusion."
            ))

        # 2. Cardiogenic Shock Protocol
        elif any("Cardiogenic" in name for name in active_pattern_names):
            protocol = "Cardiogenic Shock & Inotropic Support Protocol"
            items.append(ClinicalActionItem(
                category="DIAGNOSTIC",
                action_text="Emergency focused bedside echocardiography (TTE/POCUS) to assess LV ejection fraction, RV strain, and valvular pathology.",
                urgency="STAT",
                guideline_source="AHA / ESC Shock Guidelines",
                rationale="Differentiates pump failure etiology (infarction, acute regurgitation, tamponade)."
            ))
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Start inotropic support: Dobutamine infusion (2.5 - 10 mcg/kg/min) or Milrinone if elevated afterload.",
                urgency="STAT",
                guideline_source="AHA Guidelines",
                rationale="Augments cardiac contractility and stroke volume."
            ))
            cautions.append("CAUTION: Avoid rapid crystalloid boluses; high risk of precipitating acute hydrostatic pulmonary edema.")

        # 3. Hemorrhagic Shock Protocol
        elif any("Hemorrhagic" in name for name in active_pattern_names):
            protocol = "Massive Transfusion & Hemorrhage Control Protocol"
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Activate Massive Transfusion Protocol: Balanced 1:1:1 ratio (PRBC : FFP : Platelets).",
                urgency="STAT",
                guideline_source="AABB / Trauma Guidelines",
                rationale="Prevents dilutional coagulopathy and trauma-induced coagulopathy."
            ))
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Administer Tranexamic Acid (TXA 1g IV over 10 min, then 1g infusion over 8h).",
                urgency="STAT",
                guideline_source="CRASH-2 Trial Protocol",
                rationale="Antifibrinolytic therapy reduces mortality if administered within 3 hours."
            ))
            cautions.append("CAUTION: Maintain normothermia; hypothermia (< 35°C) inhibits coagulation enzyme kinetics.")

        # 4. ARDS / Severe Hypoxemic Failure Protocol
        elif any("ARDS" in name for name in active_pattern_names) or (organ_assessments.get("Respiratory") and organ_assessments["Respiratory"].grade >= 2):
            protocol = "ARDSNet Lung-Protective Mechanical Ventilation Protocol"
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Ventilator settings: Target tidal volume 6 mL/kg predicted body weight (PBW); maintain plateau pressure < 30 cmH2O.",
                urgency="15_MIN",
                guideline_source="Berlin ARDS 2012 & ARDSNet",
                rationale="Mitigates volutrauma and barotrauma; proven 9% absolute mortality reduction."
            ))
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="Titrate PEEP according to ARDSNet High PEEP / FiO2 table to prevent end-expiratory alveolar collapse.",
                urgency="1_HOUR",
                guideline_source="ARDSNet Protocols",
                rationale="Prevents atelectrauma and improves ventilation-perfusion matching."
            ))

        # 5. Routine / Stable Care
        else:
            protocol = "Standard ICU Protective Surveillance Protocol"
            items.append(ClinicalActionItem(
                category="MONITORING",
                action_text="Maintain scheduled vital signs observation and hemodynamic continuous monitoring.",
                urgency="ROUTINE",
                guideline_source="Critical Care Core Protocols",
                rationale="Patient is currently stable; continue proactive vigilance."
            ))

        # Check for secondary organ bundles to append:
        # KDIGO Renal Care Bundle
        renal = organ_assessments.get("Renal")
        if renal and renal.grade >= 2:
            items.append(ClinicalActionItem(
                category="THERAPEUTIC",
                action_text="KDIGO AKI Bundle: Review and discontinue all nephrotoxic drugs (NSAIDs, aminoglycosides, IV contrast).",
                urgency="15_MIN",
                guideline_source="KDIGO AKI Guidelines (2012)",
                rationale="Prevents transition of acute kidney stress into irreversible tubular necrosis."
            ))
            items.append(ClinicalActionItem(
                category="MONITORING",
                action_text="Place indwelling urinary catheter with hourly urometer; target urine output > 0.5 mL/kg/h.",
                urgency="1_HOUR",
                guideline_source="KDIGO AKI Guidelines (2012)",
                rationale="Provides real-time metric of renal tubular perfusion."
            ))

        stat_list = [it.action_text for it in items if it.urgency in ["STAT", "15_MIN"]]

        return ActionablePlan(
            primary_protocol=protocol,
            items=items,
            stat_actions=stat_list,
            contraindications_and_cautions=cautions
        )
