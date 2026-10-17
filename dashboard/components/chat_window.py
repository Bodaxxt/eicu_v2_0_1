"""
ICU Guard v5.0 — LLM Copilot Chat Window Component
====================================================
Embedded bedside chat panel connecting to ``BedsideClinicalChat``:
- Scrollable conversation history with user / copilot bubbles
- Typing indicator during async inference
- Online / Offline provider badge
- Multi-turn context preserved across questions
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, Optional, List
from nicegui import ui

from severity_agent.llm_copilot.chat import BedsideClinicalChat
from severity_agent.llm_copilot.client import AutoClient


class ChatWindow:
    """Self-contained NiceGUI chat window backed by ``BedsideClinicalChat``.

    Usage::

        cw = ChatWindow(assessment_dict, patient_vitals)
        cw.render()
    """

    def __init__(
        self,
        assessment_dict: Dict[str, Any],
        patient_vitals: Dict[str, Any],
        llm_client: Optional[Any] = None,
    ) -> None:
        self._assessment = assessment_dict
        self._vitals = patient_vitals
        self._chat = BedsideClinicalChat(client=llm_client or AutoClient())
        self._messages: List[Dict[str, str]] = []
        self._msg_area: Optional[ui.scroll_area] = None
        self._input: Optional[ui.input] = None
        self._typing_label: Optional[ui.label] = None
        self._send_btn: Optional[ui.button] = None

    # ── Provider badge ─────────────────────────────────────────────────────────
    @property
    def _provider_label(self) -> str:
        client = self._chat.client
        if hasattr(client, "provider_name"):
            return client.provider_name.upper()
        if hasattr(client, "is_online") and client.is_online:
            return "ONLINE"
        return "OFFLINE (Pure Python)"

    @property
    def _is_online(self) -> bool:
        return getattr(self._chat.client, "is_online", False)

    # ── Render ─────────────────────────────────────────────────────────────────
    def render(self) -> None:
        """Render the full chat panel into the current NiceGUI container."""
        with ui.card().classes("w-full").style(
            "background: #1e293b; border: 1px solid #334155; "
            "border-radius: 12px; padding: 20px;"
        ):
            # Header
            with ui.row().classes("items-center gap-3 mb-3"):
                ui.icon("smart_toy", size="24px").style("color: #818cf8;")
                ui.label("AI Clinical Copilot").style(
                    "color: #f1f5f9; font-size: 16px; font-weight: 700;"
                )
                ui.space()
                _color = "#22c55e" if self._is_online else "#64748b"
                ui.label(self._provider_label).style(
                    f"background: {_color}22; color: {_color}; font-size: 11px; "
                    "padding: 2px 10px; border-radius: 20px; font-weight: 600;"
                )
                ui.button(icon="refresh", on_click=self._reset_session).props(
                    "flat dense round"
                ).style("color: #64748b;").tooltip("Clear session")

            # Conversation area
            self._msg_area = ui.scroll_area().style(
                "height: 340px; border: 1px solid #1e3a5f; border-radius: 8px; "
                "background: #0b1120; padding: 8px;"
            )

            # Typing indicator (hidden by default)
            self._typing_label = ui.label("Copilot is thinking…").style(
                "color: #818cf8; font-size: 12px; font-style: italic; "
                "margin: 4px 0; display: none;"
            )

            # Suggested quick-questions
            with ui.row().classes("flex-wrap gap-2 my-2"):
                for q in [
                    "Why this tier?",
                    "Fluid recommendation?",
                    "Vasopressor strategy?",
                    "Renal care bundle?",
                ]:
                    ui.button(q, on_click=lambda _, qq=q: self._send(qq)).props(
                        "outline dense"
                    ).style(
                        "font-size: 11px; color: #818cf8; border-color: #818cf844; "
                        "padding: 2px 10px; border-radius: 20px;"
                    )

            # Input row
            with ui.row().classes("items-center gap-2 mt-1"):
                self._input = ui.input(placeholder="Ask the Copilot…").classes(
                    "flex-1"
                ).style(
                    "background: #0f172a; border: 1px solid #334155; border-radius: 8px; "
                    "color: #e2e8f0; padding: 8px 12px; font-size: 13px;"
                ).props("outlined dense")
                self._input.on("keydown.enter", lambda _: self._trigger_send())

                self._send_btn = ui.button(
                    icon="send", on_click=self._trigger_send
                ).style("background: #6366f1; color: white; border-radius: 8px;")

    # ── Messaging ──────────────────────────────────────────────────────────────
    def _trigger_send(self) -> None:
        """Called on Enter key or send button."""
        if self._input and self._input.value.strip():
            asyncio.ensure_future(self._async_send(self._input.value.strip()))

    async def _async_send(self, question: str) -> None:
        """Non-blocking chat round-trip."""
        if self._input:
            self._input.set_value("")
        self._set_loading(True)
        self._add_bubble(question, role="user")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._chat.ask(
                    question,
                    assessment_summary=self._assessment,
                    patient_vitals=self._vitals,
                ),
            )
        except Exception as exc:
            response = f"⚠️ Copilot error: {exc}"

        self._set_loading(False)
        self._add_bubble(response, role="assistant")

    async def _send(self, question: str) -> None:
        """Quick-question shortcut."""
        await self._async_send(question)

    def _add_bubble(self, text: str, role: str) -> None:
        """Append a chat bubble to the message area."""
        if not self._msg_area:
            return

        is_user = role == "user"
        bg = "#1e3a5f" if is_user else "#1e293b"
        border = "#3b82f6" if is_user else "#6366f1"
        align = "flex-end" if is_user else "flex-start"
        name = "You" if is_user else "Copilot"
        name_color = "#60a5fa" if is_user else "#a78bfa"

        self._messages.append({"role": role, "content": text})

        with self._msg_area:
            with ui.element("div").style(
                f"display: flex; flex-direction: column; align-items: {align}; "
                "margin-bottom: 10px;"
            ):
                ui.label(name).style(
                    f"color: {name_color}; font-size: 11px; font-weight: 600; margin-bottom: 2px;"
                )
                with ui.element("div").style(
                    f"background: {bg}; border: 1px solid {border}44; "
                    "border-radius: 10px; padding: 10px 14px; max-width: 85%;"
                ):
                    ui.label(text).style(
                        "color: #e2e8f0; font-size: 12px; line-height: 1.6; "
                        "white-space: pre-wrap;"
                    )

        # Scroll to bottom
        if self._msg_area:
            self._msg_area.scroll_to(percent=1.0)

    def _set_loading(self, loading: bool) -> None:
        if self._typing_label:
            self._typing_label.style(
                f"display: {'block' if loading else 'none'};"
                " color: #818cf8; font-size: 12px; font-style: italic; margin: 4px 0;"
            )
        if self._send_btn:
            self._send_btn.props("loading" if loading else "")
        if self._input:
            self._input.props("disable" if loading else "")

    def _reset_session(self) -> None:
        """Clear chat history and rebuild message area."""
        self._chat.reset_session()
        self._messages.clear()
        if self._msg_area:
            self._msg_area.clear()
        ui.notify("Chat session cleared", type="info", timeout=2000)
