"""
ICU Guard v5.0 — Patient Selection Page
Provides clinical registry navigation, tiered triage overview, live search,
patient preview dialog, and simulation bootstrapping.
"""

from typing import Dict, Any, Optional
from nicegui import ui, app

from dashboard.config import config
from dashboard.utils.constants import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    TIER_STABLE,
    ALL_TIERS,
    TIER_COLORS,
)
from dashboard.utils.data_loader import get_data_loader
from dashboard.components.patient_table import PatientTable


def patient_selection_page():
    """Renders the main clinical patient selection interface."""
    loader = get_data_loader()
    stats = loader.get_summary_stats()
    all_records = loader.get_filtered_records()

    # Page State
    selected_patient_container: Dict[str, Any] = {"patient": all_records[0] if all_records else None}

    # -------------------------------------------------------------------------
    # 1. Header Bar: Hospital Branding & Telemetry Status
    # -------------------------------------------------------------------------
    with ui.header().classes("w-full bg-slate-900 border-b border-slate-800 px-6 py-3 items-center justify-between z-20"):
        with ui.row().classes("items-center gap-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("local_hospital", size="32px", color="cyan-4")
                with ui.column().classes("gap-0"):
                    ui.label("ICU GUARD v5.0").classes("text-xl font-bold tracking-wider text-slate-100")
                    ui.label("Autonomous Severity Engine & Clinical Copilot").classes("text-xs text-slate-400 font-medium")

        with ui.row().classes("items-center gap-3"):
            with ui.row().classes("items-center gap-2 bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700"):
                ui.html('<div class="pulse-indicator"></div>')
                ui.label("SYSTEM OPERATIONAL").classes("text-xs font-semibold text-emerald-400 tracking-wide")

            ui.badge("100% Pure Python Core", color="slate-700").classes("text-xs text-slate-300 font-mono")
            ui.badge("v5.0.0", color="blue-900").classes("text-xs text-cyan-300 font-mono")
            ui.button("Live Prediction", icon="radar", on_click=lambda: ui.navigate.to("/live_prediction")).props("unelevated color=indigo-7 text-color=white size=sm").classes("font-mono font-bold shadow-md")
            ui.button("HL7 Stream", icon="sensors", on_click=lambda: ui.navigate.to("/hl7_stream")).props("unelevated color=cyan-7 text-color=white size=sm").classes("font-mono font-bold shadow-md")

    # -------------------------------------------------------------------------
    # 2. Main Body Container
    # -------------------------------------------------------------------------
    with ui.column().classes("w-full max-w-7xl mx-auto px-6 py-6 gap-6"):

        # ---------------------------------------------------------------------
        # KPI Triage Summary Cards
        # ---------------------------------------------------------------------
        with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"):
            # Total Cohort
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-blue-500"):
                ui.label("TOTAL ICU COHORT").classes("text-xs font-bold text-slate-400 tracking-wider")
                ui.label(f"{stats['total_patients']:,}").classes("text-3xl font-extrabold text-slate-100 mt-1")
                ui.label("Validated eICU Registry").classes("text-xs text-slate-400")

            # Critical
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-rose-600"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("CRITICAL (TIER 1)").classes("text-xs font-bold text-rose-400 tracking-wider")
                    ui.icon("emergency", size="20px", color="rose-500")
                ui.label(f"{stats['critical_count']:,}").classes("text-3xl font-extrabold text-rose-400 mt-1")
                ui.label(f"{stats['critical_pct']:.1f}% Resuscitation Priority").classes("text-xs text-rose-300/80")

            # High
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-orange-500"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("HIGH ACUITY (TIER 2)").classes("text-xs font-bold text-orange-400 tracking-wider")
                    ui.icon("warning_amber", size="20px", color="orange-400")
                ui.label(f"{stats['high_count']:,}").classes("text-3xl font-extrabold text-orange-400 mt-1")
                ui.label("Intensive Surveillance").classes("text-xs text-orange-300/80")

            # Moderate
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-amber-400"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("MODERATE (TIER 3)").classes("text-xs font-bold text-amber-300 tracking-wider")
                    ui.icon("watch_later", size="20px", color="amber-400")
                ui.label(f"{stats['moderate_count']:,}").classes("text-3xl font-extrabold text-amber-300 mt-1")
                ui.label("Step-Down / Regular Unit").classes("text-xs text-amber-300/80")

            # Stable
            with ui.card().classes("glass-card p-4 justify-between border-l-4 border-l-emerald-500"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("STABLE (TIER 4)").classes("text-xs font-bold text-emerald-400 tracking-wider")
                    ui.icon("check_circle", size="20px", color="emerald-400")
                ui.label(f"{stats['stable_count']:,}").classes("text-3xl font-extrabold text-emerald-400 mt-1")
                ui.label("Low Deterioration Risk").classes("text-xs text-emerald-300/80")

        # ---------------------------------------------------------------------
        # Active Selected Patient Banner & Action Launcher
        # ---------------------------------------------------------------------
        selected_banner = ui.card().classes(
            "w-full glass-card-elevated p-5 border border-cyan-500/40 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900"
        )

        def refresh_selected_banner():
            selected_banner.clear()
            p = selected_patient_container["patient"]
            with selected_banner:
                if p:
                    tier_color = TIER_COLORS.get(p.get("tier", "STABLE"), "#32CD32")
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-4"):
                        with ui.row().classes("items-center gap-4"):
                            ui.icon("person", size="36px", color="cyan-4")
                            with ui.column().classes("gap-1"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label("SELECTED PATIENT:").classes("text-xs text-cyan-300 font-mono tracking-widest")
                                    ui.label(f"#{p.get('id', 'N/A')}").classes("text-xl font-bold text-white")
                                    ui.badge(p.get("tier", "STABLE"), color="transparent").style(
                                        f"border: 1px solid {tier_color}; color: {tier_color}; background-color: {tier_color}22; font-weight: bold;"
                                    )
                                with ui.row().classes("items-center gap-3 text-xs text-slate-300 font-mono"):
                                    ui.label(f"Age: {p.get('age', 'N/A')}")
                                    ui.label("•")
                                    ui.label(f"Gender: {p.get('gender', 'N/A')}")
                                    ui.label("•")
                                    ui.label(f"APACHE IV: {p.get('apache', 'N/A')}")
                                    ui.label("•")
                                    ui.label(f"Deterioration Prob: {p.get('p_deterioration_pct', '—')}")

                        with ui.row().classes("items-center gap-3"):
                            ui.button(
                                "Quick Preview",
                                icon="visibility",
                                on_click=lambda: open_patient_preview(selected_patient_container["patient"]),
                            ).props("flat color=cyan-3")

                            ui.button(
                                "Start Simulation",
                                icon="play_arrow",
                                on_click=lambda: start_simulation(selected_patient_container["patient"]),
                            ).props("unelevated color=primary").classes("font-bold px-6")
                else:
                    ui.label("No patient currently selected. Please click on any row in the table below.").classes(
                        "text-sm text-slate-400"
                    )

        # ---------------------------------------------------------------------
        # Filter & Search Control Toolbar
        # ---------------------------------------------------------------------
        with ui.card().classes("w-full glass-card p-4"):
            with ui.row().classes("w-full items-center justify-between gap-4 flex-wrap"):
                # Left: Filter by Tier & Search
                with ui.row().classes("items-center gap-3 flex-wrap"):
                    ui.icon("filter_list", size="24px", color="slate-400")
                    ui.label("FILTER BY TIER:").classes("text-xs font-bold text-slate-400 tracking-wider")

                    tier_select = ui.select(
                        options=["ALL"] + ALL_TIERS,
                        value="ALL",
                        on_change=lambda e: apply_filters(),
                    ).props("dense outlined dark options-dense").classes("w-44")

                    search_input = ui.input(
                        placeholder="Search Patient ID, Age, Gender...",
                        on_change=lambda e: apply_filters(),
                    ).props("dense outlined dark clearable").classes("w-64")

                # Right: Quick Random & Simulation Actions
                with ui.row().classes("items-center gap-3"):
                    ui.button(
                        "Random Patient",
                        icon="shuffle",
                        on_click=lambda: select_random_patient(),
                    ).props("outlined color=cyan-3").classes("font-semibold text-xs")

                    ui.button(
                        "Start Simulation",
                        icon="rocket_launch",
                        on_click=lambda: start_simulation(selected_patient_container["patient"]),
                    ).props("unelevated color=positive").classes("font-bold text-xs px-4")

        # ---------------------------------------------------------------------
        # Patient Registry Table
        # ---------------------------------------------------------------------
        table_container = ui.column().classes("w-full")

        def handle_patient_selection(row: Dict[str, Any]) -> None:
            """Triggered when a row or preview button is clicked."""
            selected_patient_container["patient"] = row
            refresh_selected_banner()
            open_patient_preview(row)

        def handle_patient_simulate(row: Dict[str, Any]) -> None:
            """Triggered when direct select/simulate is clicked on a table row."""
            selected_patient_container["patient"] = row
            refresh_selected_banner()
            start_simulation(row)

        with table_container:
            patient_table = PatientTable(
                records=all_records,
                on_select=handle_patient_selection,
                on_simulate=handle_patient_simulate,
            )

        def apply_filters() -> None:
            """Filters records based on selected tier and search string."""
            current_tier = tier_select.value
            query = search_input.value
            filtered = loader.get_filtered_records(tier_filter=current_tier, search_query=query)
            patient_table.update_rows(filtered)

        def select_random_patient() -> None:
            """Selects a random patient from the cohort."""
            rand_patient = loader.get_random_patient()
            selected_patient_container["patient"] = rand_patient
            refresh_selected_banner()
            ui.notify(
                f"Selected Random Patient #{rand_patient.get('id')} ({rand_patient.get('tier')})",
                type="info",
                position="top-right",
            )
            open_patient_preview(rand_patient)

        def start_simulation(patient: Optional[Dict[str, Any]]) -> None:
            """Starts patient simulation and passes patient context to Stage 2."""
            if not patient:
                ui.notify("Please select a patient first.", type="warning", position="top")
                return

            pid = patient.get("id")
            tier = patient.get("tier")
            ui.notify(
                f"🚀 Bootstrapping ICU Guard Simulation for Patient #{pid} [{tier}]...",
                type="positive",
                position="top",
                close_button=True,
            )
            app.storage.user["active_patient_id"] = pid
            ui.navigate.to(f"/live_monitor?patient_id={pid}")

        # ---------------------------------------------------------------------
        # Patient Clinical Detail Modal Dialog
        # ---------------------------------------------------------------------
        preview_dialog = ui.dialog().classes("z-50")

        def open_patient_preview(patient: Dict[str, Any]) -> None:
            """Opens detailed modal preview for the selected patient."""
            if not patient:
                return

            preview_dialog.clear()
            with preview_dialog, ui.card().classes("w-[680px] max-w-[95vw] glass-card-elevated p-6 gap-4 border border-slate-700"):
                pid = patient.get("id", "Unknown")
                tier = patient.get("tier", "STABLE")
                tier_color = TIER_COLORS.get(tier, "#32CD32")

                # Dialog Title Header
                with ui.row().classes("w-full justify-between items-center border-b border-slate-700/60 pb-3"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("medical_services", size="28px", color="cyan-4")
                        with ui.column().classes("gap-0"):
                            ui.label(f"Patient File: #{pid}").classes("text-lg font-bold text-white")
                            ui.label("Clinical Assessment & Telemetry Baseline").classes("text-xs text-slate-400")

                    ui.badge(tier).style(
                        f"border: 1px solid {tier_color}; color: {tier_color}; background-color: {tier_color}22; font-weight: bold; font-size: 0.85rem; padding: 4px 10px;"
                    )

                # Patient Demographics & Scores
                with ui.row().classes("w-full grid grid-cols-2 sm:grid-cols-4 gap-3 py-2"):
                    with ui.card().classes("bg-slate-800/80 p-3 rounded-lg border border-slate-700"):
                        ui.label("AGE").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(str(patient.get("age", "N/A"))).classes("text-base font-bold text-slate-100")

                    with ui.card().classes("bg-slate-800/80 p-3 rounded-lg border border-slate-700"):
                        ui.label("GENDER").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(str(patient.get("gender", "N/A"))).classes("text-base font-bold text-slate-100")

                    with ui.card().classes("bg-slate-800/80 p-3 rounded-lg border border-slate-700"):
                        ui.label("APACHE IV").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(str(patient.get("apache", "N/A"))).classes("text-base font-bold text-slate-100")

                    with ui.card().classes("bg-slate-800/80 p-3 rounded-lg border border-slate-700"):
                        ui.label("DETERIORATION").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(patient.get("p_deterioration_pct", "0.0%")).classes("text-base font-bold text-rose-400")

                # Key Bedside Physiological Markers (from features if available)
                ui.label("BASELINE VITAL SIGNS & LAB CLEARANCE:").classes("text-xs font-bold text-slate-400 tracking-wider mt-2")
                with ui.row().classes("w-full grid grid-cols-2 sm:grid-cols-4 gap-3"):
                    # Heart Rate
                    hr = patient.get("heartrate_mean", patient.get("heartrate_max", "N/A"))
                    hr_str = f"{float(hr):.0f} bpm" if hr != "N/A" and hr is not None else "N/A"
                    with ui.card().classes("bg-slate-900/90 p-2.5 rounded border border-slate-800"):
                        ui.label("Heart Rate").classes("text-[11px] text-slate-400")
                        ui.label(hr_str).classes("text-sm font-bold text-slate-200")

                    # Mean BP
                    mbp = patient.get("meanbp_min", "N/A")
                    mbp_str = f"{float(mbp):.0f} mmHg" if mbp != "N/A" and mbp is not None else "N/A"
                    with ui.card().classes("bg-slate-900/90 p-2.5 rounded border border-slate-800"):
                        ui.label("Mean BP (Min)").classes("text-[11px] text-slate-400")
                        ui.label(mbp_str).classes("text-sm font-bold text-slate-200")

                    # SaO2
                    sao2 = patient.get("sao2_min", "N/A")
                    sao2_str = f"{float(sao2):.0f}%" if sao2 != "N/A" and sao2 is not None else "N/A"
                    with ui.card().classes("bg-slate-900/90 p-2.5 rounded border border-slate-800"):
                        ui.label("SaO2 (Min)").classes("text-[11px] text-slate-400")
                        ui.label(sao2_str).classes("text-sm font-bold text-slate-200")

                    # Serum Lactate
                    lac = patient.get("lactate_max", "N/A")
                    lac_str = f"{float(lac):.1f} mmol/L" if lac != "N/A" and lac is not None else "N/A"
                    with ui.card().classes("bg-slate-900/90 p-2.5 rounded border border-slate-800"):
                        ui.label("Serum Lactate").classes("text-[11px] text-slate-400")
                        ui.label(lac_str).classes("text-sm font-bold text-slate-200")

                # Action Recommendation Box
                rec_action = patient.get(
                    "recommended_action",
                    "Maintain continuous bedside telemetry, observe vital signs, and alert medical intensivist on acute decline."
                )
                with ui.card().classes("w-full bg-slate-900/80 p-3 rounded-lg border border-slate-700/60 mt-1"):
                    ui.label("RECOMMENDED CLINICAL PROTOCOL:").classes("text-[11px] font-bold text-amber-400 tracking-wider")
                    ui.label(str(rec_action)).classes("text-xs text-slate-300 mt-1 leading-relaxed")

                # Dialog Action Buttons
                with ui.row().classes("w-full justify-end items-center gap-3 pt-3 border-t border-slate-700/60"):
                    ui.button("Close", on_click=preview_dialog.close).props("flat color=slate-4")
                    ui.button(
                        "Start Simulation With This Patient",
                        icon="play_arrow",
                        on_click=lambda: (preview_dialog.close(), start_simulation(patient)),
                    ).props("unelevated color=primary").classes("font-bold")

            preview_dialog.open()

        # Initial Render of Selected Banner
        refresh_selected_banner()
