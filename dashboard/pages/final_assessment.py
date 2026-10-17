"""
ICU Guard v5.0 — Final Assessment Page (Phase 3)
=================================================
Full clinical decision support report page assembling all Phase 3 components:
  - Triage Header  (tier badge, escalation audit, demographics)
  - Risk Gauges    (3 Plotly semi-circular gauges)
  - Organ Cards    (11 physiological subsystems)
  - Pattern List   (16 syndrome evaluators)
  - Action List    (prioritised guideline-adherent action plan)
  - Narrative View (English / Arabic bilingual tabs)
  - Uncertainty    (reliability tier + CI bars)
  - SBAR Modal     (one-click shift handoff)
  - Chat Window    (embedded AI Copilot)
  - PDF Export     (download full report)

Route: /final_assessment?patient_id=<id>
"""

from __future__ import annotations
import asyncio
import logging
import sys
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from nicegui import ui, app

# Dashboard internals
from dashboard.config import config
from dashboard.utils.data_loader import get_data_loader
from dashboard.utils.constants import TIER_COLORS

# Phase 3 components
from dashboard.components.triage_header import render_triage_header
from dashboard.components.risk_gauges import render_risk_gauges
from dashboard.components.organ_cards import render_organ_cards
from dashboard.components.pattern_list import render_pattern_list
from dashboard.components.action_list import render_action_list
from dashboard.components.narrative_view import render_narrative_view
from dashboard.components.uncertainty_view import render_uncertainty_view
from dashboard.components.sbar_modal import open_sbar_modal
from dashboard.components.chat_window import ChatWindow

# Agent & LLM
from severity_agent.agent import SeverityAgent, FullClinicalAssessment
from severity_agent.llm_copilot import SBARGenerator, AutoClient
from dashboard.utils.pdf_export import export_pdf


# ---------------------------------------------------------------------------
# Shared singleton agent (loaded once per process)
# ---------------------------------------------------------------------------
_AGENT: Optional[SeverityAgent] = None


def _get_agent() -> SeverityAgent:
    global _AGENT
    if _AGENT is None:
        _AGENT = SeverityAgent()
    return _AGENT


# ---------------------------------------------------------------------------
# Assessment runner (called in thread-pool to avoid blocking event loop)
# ---------------------------------------------------------------------------
def _run_assessment(patient_row: Dict[str, Any]) -> FullClinicalAssessment:
    """Execute full clinical assessment synchronously (runs in executor)."""
    agent = _get_agent()
    return agent.full_assessment(patient_row)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def final_assessment_page(patient_id: Optional[str] = None) -> None:
    """Render the Phase 3 Final Assessment page.

    Args:
        patient_id: Patient identifier string passed as a query parameter.
    """
    loader = get_data_loader()

    # Resolve patient
    pid = patient_id or app.storage.user.get("active_patient_id")
    patient = loader.get_patient(pid) if pid else None
    if not patient:
        patient = loader.get_random_patient()

    patient_row: Dict[str, Any] = loader.get_patient_row(patient.get("id")) or {}
    tier_color = TIER_COLORS.get(patient.get("tier", "STABLE"), "#22c55e")

    # ── Global header ──────────────────────────────────────────────────────────
    with ui.header().classes(
        "w-full bg-slate-900 border-b border-slate-800 px-6 py-2.5 "
        "items-center justify-between z-20"
    ):
        with ui.row().classes("items-center gap-4"):
            ui.button(
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(
                    f"/live_monitor?patient_id={patient.get('id')}"
                ),
            ).props("flat round color=cyan-4").tooltip("Back to Live Monitor")

            with ui.row().classes("items-center gap-2"):
                ui.icon("summarize", size="28px", color="cyan-4")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(
                            f"FINAL ASSESSMENT • PATIENT #{patient.get('id')}"
                        ).classes("text-base font-bold text-slate-100 font-mono")
                        ui.badge(patient.get("tier", "STABLE")).style(
                            f"border: 1px solid {tier_color}; color: {tier_color}; "
                            f"background-color: {tier_color}22; font-weight: bold; "
                            "font-size: 0.7rem; padding: 2px 6px;"
                        )
                    ui.label(
                        f"Age: {patient.get('age', 'N/A')} • "
                        f"Gender: {patient.get('gender', 'N/A')} • "
                        f"APACHE IV: {patient.get('apache', 'N/A')}"
                    ).classes("text-xs text-slate-400 font-mono")

        with ui.row().classes("items-center gap-3"):
            ui.label("ICU Guard v5.0").classes("text-sm font-bold text-indigo-400")

    # ── Page body ──────────────────────────────────────────────────────────────
    with ui.column().classes("w-full gap-6").style(
        "background: #0b1120; min-height: 100vh; padding: 88px 24px 40px;"
    ):
        # Loading state while agent runs
        loading_card = ui.card().classes("w-full").style(
            "background: #1e293b; border: 1px solid #334155; "
            "border-radius: 12px; padding: 32px; text-align: center;"
        )
        with loading_card:
            with ui.column().classes("items-center gap-4"):
                ui.spinner("dots", size="48px").style("color: #6366f1;")
                ui.label("Running full clinical assessment…").style(
                    "color: #94a3b8; font-size: 14px;"
                )
                ui.label(
                    "Evaluating 11 organ systems, 16 syndrome patterns, "
                    "uncertainty quantification…"
                ).style("color: #64748b; font-size: 12px;")

        # Containers filled after assessment completes
        content_col = ui.column().classes("w-full gap-6")
        content_col.set_visibility(False)

        async def _run_and_render() -> None:
            """Run agent in executor then render all components."""
            try:
                loop = asyncio.get_event_loop()
                assessment: FullClinicalAssessment = await loop.run_in_executor(
                    None, _run_assessment, patient_row
                )
            except Exception as exc:
                loading_card.clear()
                with loading_card:
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("error_outline", size="28px").style("color: #ef4444;")
                        ui.label(f"Assessment failed: {exc}").style(
                            "color: #ef4444; font-size: 14px;"
                        )
                return

            # Hide loading card
            loading_card.set_visibility(False)
            content_col.set_visibility(True)

            a_dict = assessment.to_dict()
            sbar_gen = SBARGenerator(client=AutoClient())

            def _handle_sbar():
                open_sbar_modal(
                    assessment_dict=a_dict,
                    patient_vitals=patient_row,
                    sbar_generator=sbar_gen,
                )

            async def _handle_chat():
                await ui.run_javascript(
                    "document.getElementById('bedside-chat-card')?.scrollIntoView({behavior: 'smooth'});"
                )

            async def _export_pdf():
                try:
                    loop2 = asyncio.get_event_loop()
                    sbar_txt = await loop2.run_in_executor(
                        None,
                        lambda: sbar_gen.generate(a_dict, patient_row),
                    )
                    pdf_bytes = await loop2.run_in_executor(
                        None,
                        lambda: export_pdf(
                            patient_id=patient.get("id"),
                            assessment_dict=a_dict,
                            patient_vitals=patient_row,
                            english_report=assessment.english_report or "",
                            sbar_text=sbar_txt,
                        ),
                    )
                    ui.download(
                        pdf_bytes,
                        filename=f"ICU_Guard_Report_P{patient.get('id')}.pdf",
                        media_type="application/pdf",
                    )
                    ui.notify(
                        "PDF downloaded successfully!",
                        type="positive",
                        timeout=3000,
                    )
                except Exception as exc:
                    ui.notify(f"PDF export failed: {exc}", type="negative")

            with content_col:
                # 1. Triage Header
                try:
                    render_triage_header(
                        patient=patient_row,
                        assessment=assessment,
                        on_sbar=_handle_sbar,
                        on_chat=_handle_chat,
                        on_pdf=_export_pdf,
                    )
                except Exception as exc:
                    logger.error("Failed to render triage header: %s", exc)
                    ui.label(f"Header rendering error: {exc}").classes("text-rose-400 text-xs")

                # 2. Risk Gauges (full width)
                try:
                    render_risk_gauges(assessment)
                except Exception as exc:
                    logger.error("Failed to render risk gauges: %s", exc)
                    ui.label(f"Risk gauges error: {exc}").classes("text-rose-400 text-xs")

                # 3. Main two-column grid
                with ui.grid(columns=2).classes("w-full gap-6"):
                    # Left column
                    with ui.column().classes("gap-6"):
                        try:
                            render_organ_cards(assessment.organ_assessments)
                        except Exception as exc:
                            logger.error("Failed to render organ cards: %s", exc)
                            ui.label(f"Organ cards error: {exc}").classes("text-rose-400 text-xs")

                        try:
                            render_action_list(assessment.recommendations)
                        except Exception as exc:
                            logger.error("Failed to render action list: %s", exc)
                            ui.label(f"Action list error: {exc}").classes("text-rose-400 text-xs")

                    # Right column
                    with ui.column().classes("gap-6"):
                        try:
                            render_pattern_list(assessment.patterns)
                        except Exception as exc:
                            logger.error("Failed to render pattern list: %s", exc)
                            ui.label(f"Pattern list error: {exc}").classes("text-rose-400 text-xs")

                        try:
                            render_uncertainty_view(assessment.uncertainty)
                        except Exception as exc:
                            logger.error("Failed to render uncertainty view: %s", exc)
                            ui.label(f"Uncertainty view error: {exc}").classes("text-rose-400 text-xs")

                # 4. Narrative (full width)
                try:
                    render_narrative_view(assessment.english_report, assessment.arabic_report)
                except Exception as exc:
                    logger.error("Failed to render narrative view: %s", exc)
                    ui.label(f"Narrative error: {exc}").classes("text-rose-400 text-xs")

                # 5. Chat Window (full width)
                try:
                    with ui.element("div").props('id="bedside-chat-card"').classes("w-full"):
                        chat = ChatWindow(
                            assessment_dict=a_dict,
                            patient_vitals=patient_row,
                        )
                        chat.render()
                except Exception as exc:
                    logger.error("Failed to render chat window: %s", exc)
                    ui.label(f"Chat error: {exc}").classes("text-rose-400 text-xs")

                # 6. Action buttons row
                with ui.row().classes("items-center gap-4 justify-end mt-2"):
                    # SBAR button
                    ui.button(
                        "SBAR Handoff",
                        icon="swap_horiz",
                        on_click=_handle_sbar,
                    ).style(
                        "background: #0e7490; color: white; "
                        "border-radius: 8px; padding: 8px 18px;"
                    )

                    # PDF export button
                    ui.button(
                        "Export PDF",
                        icon="picture_as_pdf",
                        on_click=_export_pdf,
                    ).style(
                        "background: #7c3aed; color: white; "
                        "border-radius: 8px; padding: 8px 18px;"
                    )

                    # Restart assessment
                    ui.button(
                        "Re-assess",
                        icon="refresh",
                        on_click=lambda: ui.navigate.to(
                            f"/final_assessment?patient_id={patient.get('id')}"
                        ),
                    ).style(
                        "background: #1e293b; color: #94a3b8; "
                        "border: 1px solid #334155; border-radius: 8px; padding: 8px 18px;"
                    )

        ui.timer(0.05, _run_and_render, once=True)
