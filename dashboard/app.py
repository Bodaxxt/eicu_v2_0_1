"""
ICU Guard v5.0 — Main NiceGUI Dashboard Application
Configures routes, assets, dark mode theme, and starts WebSocket runtime.
"""

import sys
import io
import os
from typing import Optional
from pathlib import Path
from nicegui import ui, app

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from dashboard.config import config
from dashboard.pages.patient_selection import patient_selection_page
from dashboard.pages.live_monitor import live_monitor_page
from dashboard.pages.final_assessment import final_assessment_page
from dashboard.pages.hl7_stream import hl7_stream_page
from dashboard.pages.live_prediction import live_prediction_page

# -----------------------------------------------------------------------------
# Static Assets & Styling Mounting
# -----------------------------------------------------------------------------
if config.ASSETS_DIR.exists():
    app.add_static_files("/assets", str(config.ASSETS_DIR))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces Content-Security-Policy with 'unsafe-eval' and 'unsafe-inline' for Plotly/Vue."""
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
            "script-src * 'unsafe-inline' 'unsafe-eval'; "
            "style-src * 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src * data: https://fonts.gstatic.com; "
            "connect-src * ws: wss:; "
            "img-src * data: blob:;"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


def init_theme():
    """Initializes clinical dark mode and global stylesheet with permissive CSP."""
    ui.dark_mode().enable()
    ui.add_head_html("""
        <link rel="stylesheet" href="/assets/style.css">
    """)


# -----------------------------------------------------------------------------
# Application Page Routes
# -----------------------------------------------------------------------------
@ui.page("/")
def index():
    """Default Root Page -> Patient Selection Registry."""
    init_theme()
    patient_selection_page()


@ui.page("/patient_selection")
def route_patient_selection():
    """Explicit route for patient selection page."""
    init_theme()
    patient_selection_page()


@ui.page("/simulation")
def route_simulation(patient_id: Optional[str] = None):
    """Phase 2: Real-Time Physiological Telemetry Simulation Monitor."""
    init_theme()
    live_monitor_page(patient_id=patient_id)


@ui.page("/live_monitor")
def route_live_monitor(patient_id: Optional[str] = None):
    """Phase 2: Dedicated Live Bedside Telemetry Monitor."""
    init_theme()
    live_monitor_page(patient_id=patient_id)


@ui.page("/final_assessment")
def route_final_assessment(patient_id: Optional[str] = None):
    """Phase 3: Final Clinical Assessment Report."""
    init_theme()
    final_assessment_page(patient_id=patient_id)


@ui.page("/hl7_stream")
def route_hl7_stream():
    """Phase 7: HL7 Real-Time Ingestion Stream & Device Gateway."""
    init_theme()
    hl7_stream_page()


@ui.page("/live_prediction")
def route_live_prediction(patient_id: Optional[str] = None):
    """Continuous 5-Minute Prediction & Longitudinal Trajectory Dashboard."""
    init_theme()
    live_prediction_page(patient_id=patient_id)

def main():
    """Entry point to start the NiceGUI application server."""
    print("=" * 70)
    print(" ICU GUARD v5.0 — STARTING NICEGUI CLINICAL DASHBOARD")
    print(f" URL: http://{config.HOST}:{config.PORT}")
    print("=" * 70)

    ui.run(
        title=config.APP_TITLE,
        host=config.HOST,
        port=config.PORT,
        dark=config.DARK_MODE,
        reload=config.RELOAD,
        storage_secret="icu_guard_v5_secret_session_key_2026",
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
