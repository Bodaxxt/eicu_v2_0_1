"""
ICU Guard v5.0 — SBAR Modal Component
======================================
Renders the standardised SBAR (Situation–Background–Assessment–Recommendation)
clinical shift-handoff document inside a NiceGUI dialog modal with:
- Full SBAR text display
- Copy to clipboard
- Download as .txt
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict
from nicegui import ui

if TYPE_CHECKING:
    from severity_agent.llm_copilot.sbar import SBARGenerator


def open_sbar_modal(
    assessment_dict: Dict[str, Any],
    patient_vitals: Dict[str, Any],
    sbar_generator: "SBARGenerator",
    shift_notes: str = "",
) -> None:
    """Generate and display the SBAR handoff document in a modal dialog.

    Args:
        assessment_dict:  ``FullClinicalAssessment.to_dict()`` output.
        patient_vitals:   Raw vitals dict for the patient row.
        sbar_generator:   ``SBARGenerator`` instance.
        shift_notes:      Optional free-text notes from the bedside clinician.
    """
    try:
        sbar_text = sbar_generator.generate(
            assessment_summary=assessment_dict,
            patient_vitals=patient_vitals,
            shift_notes=shift_notes,
        )
    except Exception as exc:
        ui.notify(f"SBAR generation failed: {exc}", type="negative")
        return

    with ui.dialog() as dialog, ui.card().style(
        "background: #0f172a; border: 1px solid #334155; border-radius: 14px; "
        "max-width: 780px; width: 100%; padding: 24px;"
    ):
        # ── Header ─────────────────────────────────────────────────────────────
        with ui.row().classes("items-center gap-3 mb-4"):
            ui.icon("swap_horiz", size="28px").style("color: #06b6d4;")
            with ui.column().classes("gap-0"):
                ui.label("SBAR Clinical Shift Handoff").style(
                    "color: #f1f5f9; font-size: 18px; font-weight: 700;"
                )
                ui.label("Situation · Background · Assessment · Recommendation").style(
                    "color: #64748b; font-size: 12px;"
                )
            ui.space()
            ui.button(icon="close", on_click=dialog.close).props("flat dense round").style(
                "color: #64748b;"
            )

        # ── SBAR sections coloured ─────────────────────────────────────────────
        _render_sbar_sections(sbar_text)

        # ── Actions ────────────────────────────────────────────────────────────
        ui.separator().style("margin: 16px 0; border-color: #334155;")
        with ui.row().classes("gap-2 justify-end"):
            async def _copy():
                await ui.run_javascript(
                    f"navigator.clipboard.writeText({repr(sbar_text)});"
                )
                ui.notify("SBAR copied!", type="positive", timeout=2000)

            async def _download():
                ui.download(
                    sbar_text.encode("utf-8"),
                    filename="SBAR_Handoff.txt",
                    media_type="text/plain",
                )

            ui.button("Copy", icon="content_copy", on_click=_copy).props("outline").style(
                "color: #06b6d4; border-color: #06b6d4;"
            )
            ui.button("Download .txt", icon="download", on_click=_download).style(
                "background: #0e7490; color: white;"
            )
            ui.button("Close", on_click=dialog.close).style(
                "background: #1e293b; color: #94a3b8;"
            )

    dialog.open()


def _render_sbar_sections(sbar_text: str) -> None:
    """Parse and render SBAR sections with distinct colour coding."""
    section_colors = {
        "[S]": ("#ef4444", "Situation"),
        "[B]": ("#f97316", "Background"),
        "[A]": ("#eab308", "Assessment"),
        "[R]": ("#22c55e", "Recommendation"),
    }

    with ui.scroll_area().style(
        "height: 420px; border: 1px solid #1e3a5f; border-radius: 8px; "
        "background: rgba(0,0,0,0.25); padding: 4px;"
    ):
        lines = sbar_text.split("\n")
        current_color = "#94a3b8"
        buffer: list[str] = []

        def flush(color: str):
            if buffer:
                block = "\n".join(buffer).strip()
                if block:
                    ui.label(block).style(
                        f"color: {color}; font-family: 'Courier New', monospace; "
                        "font-size: 12px; line-height: 1.7; white-space: pre-wrap; "
                        "padding: 6px 12px; display: block;"
                    )
                buffer.clear()

        for line in lines:
            matched = None
            for tag, (color, _) in section_colors.items():
                if tag in line:
                    flush(current_color)
                    current_color = color
                    matched = True
                    buffer.append(line)
                    break
            if not matched:
                buffer.append(line)

        flush(current_color)
