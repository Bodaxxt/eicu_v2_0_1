"""
ICU Guard v5.0 — Uncertainty View Component
============================================
Renders the full UncertaintyReport as an interactive visual panel:
- Reliability tier badge (RELIABLE / CAUTION / HIGH_UNCERTAINTY)
- Composite, Epistemic, Aleatoric and OOD score gauges (Plotly)
- Per-target confidence interval bars
- Clinical advisory callout
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from nicegui import ui

if TYPE_CHECKING:
    from severity_agent.uncertainty import UncertaintyReport

# Tier colours
_TIER_META: dict[str, dict] = {
    "RELIABLE":         {"color": "#22c55e", "bg": "rgba(34,197,94,0.12)",  "icon": "verified"},
    "CAUTION":          {"color": "#eab308", "bg": "rgba(234,179,8,0.12)",  "icon": "warning"},
    "HIGH_UNCERTAINTY": {"color": "#ef4444", "bg": "rgba(239,68,68,0.12)",  "icon": "gpp_bad"},
}


def render_uncertainty_view(uncertainty: "UncertaintyReport | Any | None") -> None:
    """Render the uncertainty quantification card."""
    if hasattr(uncertainty, "uncertainty"):
        uncertainty = uncertainty.uncertainty
    with ui.card().classes("w-full").style(
        "background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px;"
    ):
        with ui.row().classes("items-center gap-3 mb-4"):
            ui.icon("analytics", size="24px").style("color: #8b5cf6;")
            ui.label("Model Uncertainty & Reliability").style(
                "color: #f1f5f9; font-size: 16px; font-weight: 700;"
            )

        if not uncertainty:
            ui.label("Uncertainty report unavailable.").style(
                "color: #64748b; font-style: italic;"
            )
            return

        tier_meta = _TIER_META.get(uncertainty.reliability_tier, _TIER_META["CAUTION"])

        # ── Reliability Tier Banner ────────────────────────────────────────────
        with ui.row().classes("items-center gap-3 mb-4").style(
            f"background: {tier_meta['bg']}; border: 1px solid {tier_meta['color']}44; "
            "padding: 12px 16px; border-radius: 10px;"
        ):
            ui.icon(tier_meta["icon"], size="28px").style(f"color: {tier_meta['color']};")
            with ui.column().classes("gap-0"):
                ui.label(uncertainty.reliability_tier.replace("_", " ")).style(
                    f"color: {tier_meta['color']}; font-size: 16px; font-weight: 700;"
                )
                ui.label("Reliability Assessment").style(
                    "color: #94a3b8; font-size: 12px;"
                )

        # ── Score Grid ─────────────────────────────────────────────────────────
        with ui.grid(columns=4).classes("w-full gap-3 mb-4"):
            _score_tile("Composite", uncertainty.composite_uncertainty_score, "#8b5cf6")
            _score_tile("Epistemic",  uncertainty.epistemic_score,            "#60a5fa")
            _score_tile("Aleatoric",  uncertainty.aleatoric_score,            "#f472b6")
            _score_tile("OOD Score",  uncertainty.ood_score,                  "#fb923c")

        # ── Per-Target Intervals ───────────────────────────────────────────────
        if uncertainty.targets:
            ui.label("Predictive Confidence Intervals (90% conformal)").style(
                "color: #94a3b8; font-size: 13px; font-weight: 600; margin-bottom: 8px;"
            )
            for tgt_name, t in uncertainty.targets.items():
                _render_ci_bar(tgt_name, t)

        # ── Clinical Advisory ──────────────────────────────────────────────────
        ui.separator().style("margin: 16px 0; border-color: #334155;")
        with ui.row().classes("items-start gap-2").style(
            "background: rgba(139,92,246,0.08); border: 1px solid #8b5cf644; "
            "padding: 10px 14px; border-radius: 8px;"
        ):
            ui.icon("smart_toy", size="16px").style(
                "color: #a78bfa; margin-top: 2px; flex-shrink: 0;"
            )
            ui.label(uncertainty.clinical_advisory).style(
                "color: #c4b5fd; font-size: 12px; line-height: 1.6;"
            )


def _score_tile(label: str, value: float, color: str) -> None:
    """Render a small coloured score tile."""
    pct = int(value * 100)
    with ui.card().style(
        f"background: {color}18; border: 1px solid {color}44; "
        "border-radius: 8px; padding: 12px; text-align: center;"
    ):
        ui.label(f"{pct}%").style(
            f"color: {color}; font-size: 22px; font-weight: 700;"
        )
        ui.label(label).style("color: #94a3b8; font-size: 11px;")

        # Mini progress bar
        with ui.element("div").style(
            "width: 100%; height: 4px; background: #1e293b; "
            "border-radius: 2px; margin-top: 6px; overflow: hidden;"
        ):
            ui.element("div").style(
                f"width: {pct}%; height: 100%; background: {color}; "
                "border-radius: 2px; transition: width 0.6s ease;"
            )


def _render_ci_bar(name: str, target) -> None:
    """Render a single target confidence interval bar."""
    lo = int(target.conformal_lower * 100)
    hi = int(target.conformal_upper * 100)
    pt = int(target.point_estimate * 100)
    width = hi - lo

    with ui.row().classes("items-center gap-3 mb-2"):
        ui.label(name.capitalize()).style(
            "color: #cbd5e1; font-size: 12px; font-weight: 600; min-width: 90px;"
        )
        # Track
        with ui.element("div").style(
            "flex: 1; height: 14px; background: #0f172a; border-radius: 7px; "
            "position: relative; overflow: visible;"
        ):
            # CI band
            ui.element("div").style(
                f"position: absolute; left: {lo}%; width: {width}%; height: 100%; "
                "background: rgba(99,102,241,0.4); border-radius: 7px;"
            )
            # Point estimate marker
            ui.element("div").style(
                f"position: absolute; left: calc({pt}% - 3px); top: -3px; "
                "width: 6px; height: 20px; background: #818cf8; border-radius: 3px;"
            )
        ui.label(f"[{lo}%–{hi}%]").style(
            "color: #64748b; font-size: 11px; min-width: 80px; text-align: right;"
        )
