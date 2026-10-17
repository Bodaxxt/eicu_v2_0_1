"""
mllp_server.py — MLLP (Minimal Lower Layer Protocol) TCP Server & Client
========================================================================
Implements the MLLP protocol standard used by HL7 v2.x over TCP/IP.

MLLP Framing:
    <VT> [HL7 Message Content] <FS> <CR>
    - <VT> (0x0B, Vertical Tab): Start of Block
    - <FS> (0x1C, File Separator): End of Block
    - <CR> (0x0D, Carriage Return): End of Frame

Default Port: 6661 (standard healthcare integration port)
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Callable, Optional, Awaitable

from .segments import ACK
from .message_builder import MLLP_START, MLLP_END, MLLP_CR

logger = logging.getLogger("hl7_simulator.mllp")

VT_BYTE = 0x0B
FS_BYTE = 0x1C
CR_BYTE = 0x0D


class MLLPProtocolError(Exception):
    """Raised when an MLLP framing violation occurs."""
    pass


class MLLPServer:
    """
    Asynchronous MLLP TCP Server.

    Receives HL7 v2.x messages framed with MLLP, dispatches them
    to an optional handler callback, and responds with HL7 ACK messages.

    Args:
        host: Host/interface to bind (default: '0.0.0.0')
        port: TCP port to listen on (default: 6661)
        on_message: Optional async callback `func(raw_hl7_str) -> None | response_ack_str`
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6661,
        on_message: Optional[Callable[[str], Optional[Awaitable[Optional[str]]]]] = None,
    ):
        self.host = host
        self.port = port
        self.on_message = on_message
        self._server: Optional[asyncio.AbstractServer] = None
        self._is_running = False

    async def start(self) -> None:
        """Start listening for incoming MLLP connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._is_running = True
        logger.info(f"[MLLP Server] Listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the MLLP server and close active sockets."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._is_running = False
            logger.info("[MLLP Server] Stopped.")

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        logger.debug(f"[MLLP Server] Client connected from {client_addr}")

        buffer = bytearray()
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer.extend(chunk)

                # Process all complete MLLP frames in the buffer
                while True:
                    vt_idx = buffer.find(bytes([VT_BYTE]))
                    if vt_idx == -1:
                        buffer.clear()
                        break

                    fs_cr_idx = buffer.find(bytes([FS_BYTE, CR_BYTE]), vt_idx)
                    if fs_cr_idx == -1:
                        # Incomplete frame, wait for more data
                        if vt_idx > 0:
                            del buffer[:vt_idx]
                        break

                    # Extract HL7 payload between VT and FS
                    msg_bytes = buffer[vt_idx + 1:fs_cr_idx]
                    del buffer[:fs_cr_idx + 2]

                    raw_msg = msg_bytes.decode("utf-8", errors="replace")
                    logger.info(f"[MLLP Server] Received HL7 message ({len(raw_msg)} chars)")

                    # Parse message control ID for ACK
                    msg_id = self._extract_message_id(raw_msg)
                    sending_app, sending_fac = self._extract_source(raw_msg)

                    custom_ack = None
                    if self.on_message:
                        try:
                            res = self.on_message(raw_msg)
                            if asyncio.iscoroutine(res):
                                custom_ack = await res
                            else:
                                custom_ack = res
                        except Exception as e:
                            logger.error(f"[MLLP Server] Error in on_message callback: {e}")

                    ack_str = custom_ack or ACK(
                        original_msg_id=msg_id or "UNKNOWN",
                        ack_code="AA",
                        receiving_app=sending_app or "SENDER",
                        receiving_fac=sending_fac or "FACILITY",
                    ).build()

                    # Send ACK wrapped in MLLP frame
                    ack_frame = f"{MLLP_START}{ack_str}{MLLP_END}{MLLP_CR}".encode("utf-8")
                    writer.write(ack_frame)
                    await writer.drain()
                    logger.debug(f"[MLLP Server] Sent ACK for {msg_id}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[MLLP Server] Client handler exception: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"[MLLP Server] Connection closed for {client_addr}")

    @staticmethod
    def _extract_message_id(hl7_str: str) -> str:
        """Extract MSH-10 (Message Control ID) from raw HL7."""
        for line in hl7_str.replace("\n", "\r").split("\r"):
            if line.startswith("MSH"):
                parts = line.split("|")
                if len(parts) > 10:
                    return parts[9]
        return "UNKNOWN"

    @staticmethod
    def _extract_source(hl7_str: str) -> tuple[str, str]:
        """Extract MSH-3 (Sending Application) and MSH-4 (Sending Facility)."""
        for line in hl7_str.replace("\n", "\r").split("\r"):
            if line.startswith("MSH"):
                parts = line.split("|")
                app = parts[2] if len(parts) > 2 else ""
                fac = parts[3] if len(parts) > 3 else ""
                return app, fac
        return "", ""


class MLLPClient:
    """
    Synchronous / Asynchronous MLLP TCP Client.
    Used by simulators and tests to send HL7 messages to an MLLP server.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6661, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_message_sync(self, hl7_string: str) -> str:
        """Send an HL7 string wrapped in MLLP synchronously and wait for ACK."""
        frame = f"{MLLP_START}{hl7_string}{MLLP_END}{MLLP_CR}".encode("utf-8")

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(frame)
            # Read ACK until FS + CR
            response = bytearray()
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
                if bytes([FS_BYTE, CR_BYTE]) in response:
                    break

            # Strip MLLP framing
            vt_idx = response.find(bytes([VT_BYTE]))
            fs_idx = response.find(bytes([FS_BYTE]))
            if vt_idx != -1 and fs_idx != -1:
                return response[vt_idx + 1:fs_idx].decode("utf-8", errors="replace")
            return response.decode("utf-8", errors="replace")

    async def send_message(self, hl7_string: str) -> str:
        """Send an HL7 string wrapped in MLLP asynchronously and wait for ACK."""
        frame = f"{MLLP_START}{hl7_string}{MLLP_END}{MLLP_CR}".encode("utf-8")
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            writer.write(frame)
            await writer.drain()

            buffer = bytearray()
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
                if not chunk:
                    break
                buffer.extend(chunk)
                if bytes([FS_BYTE, CR_BYTE]) in buffer:
                    break

            vt_idx = buffer.find(bytes([VT_BYTE]))
            fs_idx = buffer.find(bytes([FS_BYTE]))
            if vt_idx != -1 and fs_idx != -1:
                return buffer[vt_idx + 1:fs_idx].decode("utf-8", errors="replace")
            return buffer.decode("utf-8", errors="replace")
        finally:
            writer.close()
            await writer.wait_closed()
