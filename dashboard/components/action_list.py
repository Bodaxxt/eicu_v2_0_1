"""
ICU Guard v5.0 — Prioritized Clinical Action List Component
===========================================================
Renders guideline-adherent bedside interventions grouped by urgency tier:
STAT → 15_MIN → 1_HOUR → ROUTINE, with colour-coded badges and expandable rationale.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from nicegui import ui

if TYPE_CHECKING:
    from severity_agent.recommendations import ActionablePlan

# Urgency display metadata
_URGENCY_META: dict[str, dict] = {
    "STAT": {
        "label": "STAT",
        "color": "#ef4444",
        "bg": "rgba(239,68,68,0.12)",
        "border": "#ef4444",
        "icon": "emergency",
        "order": 0,
    },
    "15_MIN": {
        "label": "15 min",
        "color": "#f97316",
        "bg": "rgba(249,115,22,0.12)",
        "border": "#f97316",
        "icon": "schedule",
        "order": 1,
    },
    "1_HOUR": {
        "label": "1 hr",
        "color": "#eab308",
        "bg": "rgba(234,179,8,0.12)",
        "border": "#eab308",
        "icon": "hourglass_bottom",
        "order": 2,
    },
    "ROUTINE": {
        "label": "Routine",
        "color": "#22c55e",
        "bg": "rgba(34,197,94,0.12)",
        "border": "#22c55e",
        "icon": "check_circle",
        "order": 3,
    },
}

_CATEGORY_ICON: dict[str, str] = {
    "DIAGNOSTIC": "biotech",
    "THERAPEUTIC": "medication",
    "MONITORING": "monitor_heart",
    "CONSULTATION": "support_agent",
}


def render_action_list(plan: "ActionablePlan | Any | None") -> None:
    """Render the prioritized clinical action list card."""
    if hasattr(plan, "recommendations"):
        plan = plan.recommendations
    with ui.card().classes("w-full").style(
        "background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px;"
    ):
        # ── Header ─────────────────────────────────────────────────────────────
        with ui.row().classes("items-center gap-3 mb-4"):
            ui.icon("assignment", size="24px").style("color: #6366f1;")
            ui.label("Clinical Action Plan").style(
                "color: #f1f5f9; font-size: 16px; font-weight: 700;"
            )
            if plan:
                n_stat = sum(1 for it in plan.items if it.urgency in ("STAT", "15_MIN"))
                if n_stat:
                    ui.badge(f"{n_stat} URGENT", color="red").style(
                        "font-size: 11px; font-weight: 700;"
                    )

        if not plan:
            ui.label("No action plan available.").style(
                "color: #64748b; font-style: italic;"
            )
            return

        # ── Protocol banner ────────────────────────────────────────────────────
        ui.label(f"\u25b6 Protocol: {plan.primary_protocol}").style(
            "color: #818cf8; font-size: 13px; font-weight: 600; margin-bottom: 14px;"
        )

        # ── Sort actions by urgency order ──────────────────────────────────────
        sorted_items = sorted(
            plan.items,
            key=lambda it: _URGENCY_META.get(it.urgency, {"order": 99})["order"],
        )

        for item in sorted_items:
            meta = _URGENCY_META.get(item.urgency, _URGENCY_META["ROUTINE"])
            cat_icon = _CATEGORY_ICON.get(item.category, "help_outline")

            with ui.expansion(item.action_text[:90] + ("\u2026" if len(item.action_text) > 90 else "")).style(
                f"background: {meta['bg']}; border: 1px solid {meta['border']}33; "
                "border-radius: 8px; margin-bottom: 8px;"
            ).props("dense"):
                with ui.row().classes("items-center gap-2 mb-1"):
                    ui.label(meta["label"]).style(
                        f"background: {meta['color']}22; color: {meta['color']}; "
                        "padding: 2px 8px; border-radius: 20px; font-size: 11px; "
                        "font-weight: 700; letter-spacing: 0.05em;"
                    )
                    with ui.row().classes("items-center gap-1").style(
                        "background: rgba(255,255,255,0.05); padding: 2px 8px; "
                        "border-radius: 20px;"
                    ):
                        ui.icon(cat_icon, size="14px").style("color: #94a3b8;")
                        ui.label(item.category).style(
                            "color: #94a3b8; font-size: 11px;"
                        )

                ui.label(item.action_text).style(
                    "color: #e2e8f0; font-size: 13px; margin-top: 4px;"
                )

                with ui.row().classes("items-start gap-2 mt-3").style(
                    "background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 6px;"
                ):
                    ui.icon("info_outline", size="14px").style(
                        "color: #60a5fa; margin-top: 2px; flex-shrink: 0;"
                    )
                    ui.label(item.rationale).style(
                        "color: #94a3b8; font-size: 12px; line-height: 1.5;"
                    )

                ui.label(f"\U0001f4d6 {item.guideline_source}").style(
                    "color: #64748b; font-size: 11px; margin-top: 6px; font-style: italic;"
                )

        # ── Contraindications / Cautions ───────────────────────────────────────
        if plan.contraindications_and_cautions:
            ui.separator().style("margin: 14px 0; border-color: #334155;")
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("warning_amber", size="18px").style("color: #f59e0b;")
                ui.label("Cautions & Contraindications").style(
                    "color: #f59e0b; font-size: 13px; font-weight: 600;"
                )
            for caution in plan.contraindications_and_cautions:
                with ui.row().classes("items-start gap-2 mb-1"):
                    ui.icon("report", size="14px").style(
                        "color: #f97316; margin-top: 2px; flex-shrink: 0;"
                    )
                    ui.label(caution).style(
                        "color: #fde68a; font-size: 12px; line-height: 1.5;"
                    )
