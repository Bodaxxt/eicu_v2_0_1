"""
ICU Guard v5.0 — Alert System Component
Provides floating top-right clinical alarm notifications with auto-dismiss
and client-side non-blocking Web Audio telemetry chimes.
"""

from typing import List, Optional
from nicegui import ui
from dashboard.streaming.live_analyzer import LiveAlert


class AlertSystem:
    """Manages audio-visual clinical alarms in the dashboard."""

    def __init__(self, enable_sound: bool = True):
        self.enable_sound = enable_sound
        self.alert_history: List[LiveAlert] = []

    def trigger_alert(self, alert: LiveAlert) -> None:
        """Displays a clinical alert toast in the top-right corner with sound."""
        self.alert_history.append(alert)

        # 1. Audible medical telemetry chime via Web Audio API
        if self.enable_sound:
            self._play_chime(alert.severity)

        # 2. Visual Toast with Quasar notify
        notify_type = "negative" if alert.severity == "CRITICAL" else "warning" if alert.severity == "WARNING" else "info"

        try:
            ui.notify(
                message=f"[{alert.title}] {alert.message}",
                type=notify_type,
                position="top-right",
                duration=5000,  # Auto-dismiss 5s as specified
                close_button=True,
                icon=alert.icon,
            )
        except Exception:
            pass

    def _play_chime(self, severity: str) -> None:
        """Emits a subtle synthesized medical monitor beep."""
        freq = 880 if severity == "CRITICAL" else 659
        duration = 0.22 if severity == "CRITICAL" else 0.15
        gain = 0.08 if severity == "CRITICAL" else 0.04

        js_code = f"""
        try {{
            let ctx = new (window.AudioContext || window.webkitAudioContext)();
            let osc = ctx.createOscillator();
            let gainNode = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime({freq}, ctx.currentTime);
            gainNode.gain.setValueAtTime({gain}, ctx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + {duration});
            osc.connect(gainNode);
            gainNode.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + {duration});
        }} catch (e) {{}}
        """
        try:
            ui.run_javascript(js_code)
        except Exception:
            pass
