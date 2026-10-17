"""
ICU Guard v5.0 — Clinical Narrative Generator
=============================================
Generates comprehensive, structured bilingual (English & Arabic) critical care reports:
1. Triage Level & Overall Severity Score
2. Multi-Target ML Risk Summary & Conformal Prediction Intervals
3. 11 Organ System Physiological Status
4. 16 Complex Syndrome Patterns
5. Pathophysiological Causal Graph & Trajectory Projection
6. Immediate Bedside Resuscitation Actions & Guideline Protocols
7. Ranked Differential Diagnoses with Confirming & Disconfirming Evidence
8. Uncertainty Quantification, OOD Status, and Regulatory Disclaimers
"""

from typing import Dict, Any, List, Optional
import logging

from severity_agent.detectors import OrganAssessment
from severity_agent.patterns import PatternMatch
from severity_agent.validator import ValidationReport
from severity_agent.severity import SeverityAssessment
from severity_agent.reasoning import ClinicalReasoningReport

logger = logging.getLogger(__name__)


class ClinicalNarrativeGenerator:
    """Produces structured clinical summaries in English and Arabic."""

    def generate_english_report(
        self,
        patient_id: Any,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        severity: SeverityAssessment,
        reasoning: ClinicalReasoningReport,
        validation: ValidationReport,
        uncertainty: Optional[Any] = None,
        recommendations: Optional[Any] = None
    ) -> str:
        """Generate structured English clinical report."""
        p_m = probabilities.get('p_mortality', 0.0) * 100
        p_d = probabilities.get('p_deterioration', 0.0) * 100
        p_s = probabilities.get('p_severe', 0.0) * 100

        tier_badge = {
            "CRITICAL": "[!!! CRITICAL - IMMEDIATE RESUSCITATION !!!]",
            "HIGH":     "[!! HIGH RISK - URGENT ATTENTION !!]",
            "MODERATE": "[! MODERATE RISK - CLOSE MONITORING !]",
            "STABLE":   "[ROUTINE CARE - CLINICALLY STABLE]"
        }.get(severity.final_tier, severity.final_tier)

        lines = []
        lines.append("=" * 78)
        lines.append(f"  ICU GUARD v5.0 — CLINICAL DECISION SUPPORT REPORT")
        lines.append(f"  Patient ID: {patient_id} | Triage Tier: {tier_badge}")
        lines.append("=" * 78)

        # 1. Executive Risk Summary & Conformal Bounds
        lines.append("\n1. MULTI-TARGET PREDICTIVE RISK PROFILE:")
        lines.append(f"   * 28-Day Mortality Hazard  : {p_m:5.1f}%  (Calibrated Platt Probability)")
        lines.append(f"   * 12-Hour Deterioration Risk: {p_d:5.1f}%  (Vasopressor/Ventilation Onset)")
        lines.append(f"   * Severe Disease Index      : {p_s:5.1f}%  (APACHE-Equivalent Composite)")
        lines.append(f"   * Composite Severity Score  : {severity.overall_score:.1f} / 10.0")

        if uncertainty is not None and hasattr(uncertainty, 'targets'):
            lines.append("   * Conformal Uncertainty Bounds (90% Coverage Guarantee):")
            for t_name, t_info in uncertainty.targets.items():
                lines.append(f"       - {t_name:<14}: [{t_info.conformal_lower*100:4.1f}% - {t_info.conformal_upper*100:4.1f}%] (Reliability: {uncertainty.reliability_tier})")

        # 2. Safety Overrides & Escalations
        if severity.escalation_occurred:
            lines.append("\n2. SAFETY OVERRIDE & ESCALATION AUDIT:")
            lines.append(f"   * ML Baseline Tier: {severity.ml_base_tier} -> Escalated to: {severity.final_tier}")
            for r in severity.escalation_reasons:
                lines.append(f"   * [ALERT] {r}")

        # 3. Organ Systems Breakdown (11 Subsystems)
        lines.append("\n3. ORGAN SYSTEM PHYSIOLOGICAL STATUS (11 Subsystems):")
        for name, assess in organ_assessments.items():
            sym = "[X]" if assess.grade >= 2 else ("[+]" if assess.grade == 1 else "[o]")
            lines.append(f"   {sym} {name:<14}: Grade {assess.grade} — {assess.description}")
            for ev in assess.clinical_evidence[:2]:
                lines.append(f"       -> {ev}")

        # 4. Complex Syndrome Patterns
        active_patterns = [p for p in patterns if p.detected]
        lines.append("\n4. DETECTED CLINICAL SYNDROMES & PATTERNS:")
        if active_patterns:
            for p in active_patterns:
                lines.append(f"   * [{p.urgency_tier}] {p.pattern_name} (Confidence: {p.confidence})")
                for c in p.diagnostic_criteria_met:
                    lines.append(f"       - {c}")
        else:
            lines.append("   * No high-risk multi-organ syndromes identified.")

        # 5. Clinical Reasoning & Pathophysiology
        lines.append("\n5. CLINICAL REASONING & CAUSAL GRAPH:")
        lines.append(f"   * Trajectory Velocity: {reasoning.trajectory}")
        lines.append(f"   * Causality Chain    : {reasoning.causality_narrative}")
        lines.append(f"   * Primary Etiology   : {reasoning.primary_etiology}")
        if hasattr(reasoning, 'projected_trajectory_12h') and reasoning.projected_trajectory_12h:
            proj = reasoning.projected_trajectory_12h
            lines.append(f"   * 12h Risk Projection: Projected Det={proj.get('projected_p_deterioration_12h', 0)*100:.1f}%, Velocity Multiplier={proj.get('velocity_index', 1.0)}x")

        # 6. Counterfactual Clinical Simulation
        if hasattr(reasoning, 'counterfactual_scenarios') and reasoning.counterfactual_scenarios:
            lines.append("\n6. COUNTERFACTUAL INTERVENTION MODELING:")
            for cf in reasoning.counterfactual_scenarios[:2]:
                lines.append(f"   * What-If: {cf.get('intervention')}")
                lines.append(f"     Impact : {cf.get('clinical_impact')}")

        # 7. Ranked Differential Diagnosis
        lines.append("\n7. RANKED DIFFERENTIAL DIAGNOSES (TOP 3):")
        for i, diff in enumerate(reasoning.differential_diagnosis, 1):
            lines.append(f"   {i}. {diff.diagnosis_name} (Likelihood: {diff.likelihood_pct:.1f}%)")
            lines.append(f"      Action: {diff.action_priority}")

        # 8. Recommended Immediate Clinical Actions & Protocols
        lines.append("\n8. IMMEDIATE BEDSIDE MANAGEMENT & PROTOCOLS:")
        lines.append(f"   >>> Primary Action: {severity.recommended_clinical_action}")
        if recommendations is not None and hasattr(recommendations, 'stat_actions') and recommendations.stat_actions:
            lines.append("   >>> STAT Bundle Orders:")
            for act in recommendations.stat_actions[:3]:
                lines.append(f"       * [STAT] {act}")

        # 9. Validation & Safety Disclaimers
        lines.append("\n9. VALIDATION & DECISION SUPPORT DISCLAIMER:")
        lines.append(f"   * Validation Status : {validation.clinical_sanity_status} (Confidence: {validation.confidence})")
        lines.append(f"   * Missingness Burden: {validation.missingness_rate_pct:.1f}%")
        if hasattr(validation, 'ood_detected') and validation.ood_detected:
            lines.append(f"   * OOD Alert         : Score {validation.ood_score:.2f} (Physiological anomaly detected)")
        if validation.warnings:
            for w in validation.warnings:
                lines.append(f"   * [WARNING] {w}")
        lines.append("   * DISCLAIMER: ICU Guard is an investigational SaMD tool. Final clinical")
        lines.append("     decisions rest entirely with the treating critical care physician.")
        lines.append("=" * 78)

        return "\n".join(lines)

    def generate_arabic_report(
        self,
        patient_id: Any,
        probabilities: Dict[str, float],
        organ_assessments: Dict[str, OrganAssessment],
        patterns: List[PatternMatch],
        severity: SeverityAssessment,
        reasoning: ClinicalReasoningReport,
        validation: ValidationReport,
        uncertainty: Optional[Any] = None,
        recommendations: Optional[Any] = None
    ) -> str:
        """Generate structured Arabic clinical report."""
        p_m = probabilities.get('p_mortality', 0.0) * 100
        p_d = probabilities.get('p_deterioration', 0.0) * 100
        p_s = probabilities.get('p_severe', 0.0) * 100

        arabic_tiers = {
            "CRITICAL": "حرج للغاية — يستدعي التدخل والإنعاش الفوري",
            "HIGH":     "عالي الخطورة — يتطلب تقييماً عاجلاً",
            "MODERATE": "متوسط الخطورة — مراقبة حثيثة للأجهزة",
            "STABLE":   "مستقر سريرياً — رعاية ومتابعة روتينية"
        }

        arabic_organs = {
            "Respiratory": "الجهاز التنفسي والرئة",
            "Hemodynamic": "الدورة الدموية والتروية النسيجية",
            "Renal": "الجهاز الكلوي والمسالك",
            "Neurological": "الجهاز العصبي ودرجة الوعي",
            "Sepsis": "الاستجابة الالتهابية والإنتان",
            "Hepatic": "الكبد والوظائف الكبدية",
            "Coagulation": "تخثر الدم والصفائح",
            "Metabolic": "التوازن الحمضي القاعدي والأيضي",
            "Endocrine": "الغدد الصماء والجلوكوز",
            "Hematologic": "الدم والهيموجلوبين",
            "Nutritional": "الحالة التغذوية واحتياطي الجسم"
        }

        lines = []
        lines.append("=" * 78)
        lines.append(f"  نظام ICU GUARD v5.0 — تقرير الاستدلال السريري ودعم القرار")
        lines.append(f"  رقم المريض: {patient_id} | مستوى الفرز: {arabic_tiers.get(severity.final_tier, severity.final_tier)}")
        lines.append("=" * 78)

        # 1. ملخص المخاطر
        lines.append("\n١. ملخص تقدير المخاطر السريرية وفترات عدم اليقين:")
        lines.append(f"   * احتمالية الوفاة خلال ٢٨ يوماً: {p_m:5.1f}% (احتمال معاير بـ Platt)")
        lines.append(f"   * خطر التدهور الحاد خلال ١٢ ساعة : {p_d:5.1f}% (الحاجة لمقبضات أوعية/تنفس اصطناعي)")
        lines.append(f"   * مؤشر شدة المرض العام         : {p_s:5.1f}%")
        lines.append(f"   * درجة الخطورة المركبة         : {severity.overall_score:.1f} من ١٠")

        # 2. تجاوزات الأمان
        if severity.escalation_occurred:
            lines.append("\n٢. تدقيقات الأمان ورفع مستوى الحذر:")
            lines.append(f"   * تم رفع التصنيف من ({severity.ml_base_tier}) إلى ({severity.final_tier}) بموجب بروتوكولات الأمان السريري.")
            for r in severity.escalation_reasons:
                lines.append(f"   * تنبيه: {r}")

        # 3. تقييم أجهزة الجسم الـ 11
        lines.append("\n٣. الفحص الوظيفي للأجهزة الحيوية (١١ جهازاً):")
        for name, assess in organ_assessments.items():
            ar_name = arabic_organs.get(name, name)
            lines.append(f"   * {ar_name}: درجة الإصابة {assess.grade} — {assess.description}")

        # 4. الأنماط السريرية المكتشفة
        active_patterns = [p for p in patterns if p.detected]
        lines.append("\n٤. المتلازمات والأنماط السريرية المكتشفة:")
        if active_patterns:
            for p in active_patterns:
                lines.append(f"   * متلازمة: {p.pattern_name} (مستوى الثقة: {p.confidence})")
                lines.append(f"     التوصية: {p.clinical_recommendation}")
        else:
            lines.append("   * لم يتم رصد متلازمات فشل متعدد حادة.")

        # 5. الاستدلال السريري والمسار
        lines.append("\n٥. الاستدلال السببي ومسار التدهور:")
        lines.append(f"   * مسار الحالة : {reasoning.trajectory}")
        lines.append(f"   * التسلسل السببي: {reasoning.causality_narrative}")
        lines.append(f"   * السبب الأولي : {reasoning.primary_etiology}")

        # 6. التشخيص التفريقي
        lines.append("\n٦. التشخيص التفريقي الأكثر احتمالاً (أعلى ٣ احتمالات):")
        for i, diff in enumerate(reasoning.differential_diagnosis, 1):
            lines.append(f"   {i}. {diff.diagnosis_name} (الاحتمالية: {diff.likelihood_pct:.1f}%)")

        # 7. الخطة الفورية
        lines.append("\n٧. الإجراءات السريرية الفورية المقترحة:")
        lines.append(f"   >>> {severity.recommended_clinical_action}")

        # 8. إخلاء المسؤولية والتحقق
        lines.append("\n٨. التحقق الحسابي وإخلاء المسؤولية الطبية:")
        lines.append(f"   * حالة الفحص الحسابي: {validation.clinical_sanity_status} (درجة الثقة: {validation.confidence})")
        lines.append("   * تنبيه: هذا النظام هو أداة استشارية لدعم القرار ولا يغني عن التقدير السريري المباشر لطبيب العناية المركزة.")
        lines.append("=" * 78)

        return "\n".join(lines)

