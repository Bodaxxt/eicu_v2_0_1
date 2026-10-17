"""
ICU Guard v5.0 — Bilingual Narrative View Component
====================================================
Renders the structured English / Arabic clinical narrative with tab switcher,
monospace pre-formatted text, copy-to-clipboard and expand/collapse controls.
"""

from __future__ import annotations
from typing import Any
from nicegui import ui


def render_narrative_view(english_report: Any, arabic_report: str = "") -> None:
    """Render the bilingual clinical narrative card with tab switcher."""
    if hasattr(english_report, "english_report"):
        arabic_report = getattr(english_report, "arabic_report", "") or ""
        english_report = getattr(english_report, "english_report", "") or ""
    english_report = english_report or ""
    arabic_report = arabic_report or ""
    with ui.card().classes("w-full").style(
        "background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px;"
    ):
        # ── Header ─────────────────────────────────────────────────────────────
        with ui.row().classes("items-center gap-3 mb-4"):
            ui.icon("description", size="24px").style("color: #06b6d4;")
            ui.label("Clinical Narrative Report").style(
                "color: #f1f5f9; font-size: 16px; font-weight: 700;"
            )
            ui.label("Bilingual EN / AR").style(
                "color: #64748b; font-size: 12px; margin-left: auto;"
            )

        # ── Tab switcher ───────────────────────────────────────────────────────
        with ui.tabs().props("dense align=left").style(
            "color: #818cf8; border-bottom: 1px solid #334155;"
        ) as tabs:
            tab_en = ui.tab("EN", icon="translate")
            tab_ar = ui.tab("AR", icon="language")

        with ui.tab_panels(tabs, value=tab_en).classes("w-full bg-transparent").style("width: 100%; min-width: 100%;"):
            with ui.tab_panel(tab_en).classes("w-full p-2").style("width: 100%; min-width: 100%;"):
                _render_report_block(english_report, lang="en")

            with ui.tab_panel(tab_ar).classes("w-full p-2").style("width: 100%; min-width: 100%;"):
                _render_report_block(arabic_report, lang="ar")


def _render_report_block(report: str, lang: str = "en") -> None:
    """Render a single report text block with copy button and scroll container.

    Args:
        report: Pre-formatted report string.
        lang:   ``"en"`` or ``"ar"`` — controls text direction.
    """
    if not report:
        ui.label("Report not available.").style("color: #64748b; font-style: italic;")
        return

    direction = "rtl" if lang == "ar" else "ltr"
    font = "'Courier New', monospace" if lang == "en" else "'Courier New', monospace"

    # Copy button
    async def _copy():
        await ui.run_javascript(
            f"navigator.clipboard.writeText({repr(report)});"
        )
        ui.notify("Report copied to clipboard", type="positive", timeout=2000)

    with ui.row().classes("w-full items-center justify-end mb-2"):
        ui.button("Copy", icon="content_copy", on_click=_copy).props("outline dense size=sm").style(
            "color: #06b6d4; border-color: #06b6d4;"
        ).tooltip("Copy report")

    # Scrollable text block
    with ui.scroll_area().classes("w-full").style(
        "width: 100%; min-width: 100%; height: 440px; border: 1px solid #1e3a5f; border-radius: 8px; "
        "background: rgba(0,0,0,0.45); padding: 14px;"
    ):
        ui.label(report).classes("w-full block").style(
            f"color: #cbd5e1; font-family: {font}; font-size: 12px; "
            f"line-height: 1.7; white-space: pre-wrap; word-break: break-word; direction: {direction}; "
            f"{'text-align: right;' if lang == 'ar' else 'text-align: left;'}"
        )
