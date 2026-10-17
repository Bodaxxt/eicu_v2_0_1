"""
receiver.py — Asynchronous Multi-Device MLLP HL7 Receiver
==========================================================
High-throughput asynchronous TCP MLLP server receiving continuous telemetry
from Bedside Monitors, ABG Analyzers, Central Lab, Smart Pumps, and Ventilators.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional, Awaitable

from .parser import HL7Parser, ParsedHL7Message
from hl7_simulator.core.segments import ACK
from hl7_simulator.core.message_builder import MLLP_START, MLLP_END, MLLP_CR

logger = logging.getLogger("icu_guard.hl7.receiver")

VT_BYTE = 0x0B
FS_BYTE = 0x1C
CR_BYTE = 0x0D


class HL7Receiver:
    """
    Asynchronous MLLP Server for ICU Guard.

    Args:
        host: Interface to bind (default: '0.0.0.0')
        port: Listening port (default: 6661)
        on_message: Async or sync callback invoked when a valid message is parsed
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6661,
        on_message: Optional[Callable[[ParsedHL7Message], Optional[Awaitable[None]]]] = None,
    ):
        self.host = host
        self.port = port
        self.on_message = on_message
        self._server: Optional[asyncio.AbstractServer] = None
        self._is_running = False
        self.total_messages_received = 0
        self.total_bytes_processed = 0

    async def start(self) -> None:
        """Start listening for MLLP device connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._is_running = True
        logger.info(f"[HL7Receiver] Ingestion server listening on tcp://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Close active server sockets."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._is_running = False
            logger.info("[HL7Receiver] Ingestion server stopped.")

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logger.debug(f"[HL7Receiver] Inbound connection established from {peer}")

        buffer = bytearray()
        try:
            while True:
                chunk = await reader.read(8192)
                if not chunk:
                    break
                buffer.extend(chunk)
                self.total_bytes_processed += len(chunk)

                # Process all complete MLLP frames
                while True:
                    vt_idx = buffer.find(bytes([VT_BYTE]))
                    if vt_idx == -1:
                        buffer.clear()
                        break

                    fs_cr_idx = buffer.find(bytes([FS_BYTE, CR_BYTE]), vt_idx)
                    if fs_cr_idx == -1:
                        if vt_idx > 0:
                            del buffer[:vt_idx]
                        break

                    # Slice out raw HL7 message
                    msg_bytes = buffer[vt_idx + 1:fs_cr_idx]
                    del buffer[:fs_cr_idx + 2]

                    t_start = time.perf_counter()
                    raw_msg = msg_bytes.decode("utf-8", errors="replace")
                    self.total_messages_received += 1

                    # Parse message
                    parsed = HL7Parser.parse(raw_msg)
                    msg_id = parsed.message_id if parsed else "UNKNOWN"
                    device = parsed.device if parsed else "SENDER"
                    facility = parsed.bed_id if parsed else "FACILITY"

                    # Dispatch to subscriber callback
                    if parsed and self.on_message:
                        try:
                            res = self.on_message(parsed)
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception as e:
                            logger.error(f"[HL7Receiver] Exception in message callback: {e}")

                    # Generate and return standard MLLP ACK
                    ack_str = ACK(
                        original_msg_id=msg_id,
                        ack_code="AA",
                        receiving_app=device,
                        receiving_fac=facility,
                    ).build()

                    ack_frame = f"{MLLP_START}{ack_str}{MLLP_END}{MLLP_CR}".encode("utf-8")
                    writer.write(ack_frame)
                    await writer.drain()

                    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                    logger.debug(
                        f"[HL7Receiver] Ingested message {msg_id} from {device} ({elapsed_ms:.2f} ms latency)"
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[HL7Receiver] Connection handler error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"[HL7Receiver] Connection closed for {peer}")
