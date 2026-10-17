"""
base_scenario.py — Base Class for Clinical HL7 Simulation Scenarios
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generator, List, Optional
import time

from ..core.message_builder import HL7Message
from ..core.mllp_server import MLLPClient


class BaseScenario(ABC):
    """
    Abstract Base Class for simulation scenarios.
    Each scenario yields a sequence of HL7Message objects simulating patient progression over time.
    """

    def __init__(self, patient_id: str = "224606", bed_id: str = "ICU_BED_04"):
        self.patient_id = patient_id
        self.bed_id = bed_id

    @abstractmethod
    def generate_messages(self) -> Generator[HL7Message, None, None]:
        """Generate a series of HL7 messages representing the scenario progression."""
        pass

    def run_sync(self, client: MLLPClient, interval_seconds: float = 1.0) -> List[str]:
        """
        Send all scenario messages sequentially over MLLP with a delay between them.
        Returns a list of ACKs received from the server.
        """
        acks = []
        for msg in self.generate_messages():
            ack = client.send_message_sync(msg.to_string())
            acks.append(ack)
            if interval_seconds > 0:
                time.sleep(interval_seconds)
        return acks
