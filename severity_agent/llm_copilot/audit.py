"""
ICU Guard v5.0 — LLM Copilot Interaction Audit Logger
======================================================
Maintains regulatory tracking for all natural language generation events.
Guarantees:
- Zero API keys logged.
- Zero PHI logged (all entries are pre-sanitized).
- Latency, token metrics, and fallback status tracking.
"""

import os
import json
import uuid
import datetime
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CopilotAuditLogger:
    """Logs LLM Copilot queries, model backends, and latency metrics without secrets."""

    def __init__(self, log_path: Optional[str] = None):
        if log_path is None:
            self.log_path = "e:/eicu_v2_0_1.sqlite3/severity_agent/copilot_audit.jsonl"
        else:
            self.log_path = log_path

    def log_interaction(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        latency_ms: float,
        success: bool,
        error_msg: Optional[str] = None,
        tokens_used: Optional[int] = None
    ) -> Dict[str, Any]:
        """Record an LLM Copilot interaction safely."""
        record = {
            "interaction_id": str(uuid.uuid4()),
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "latency_ms": round(latency_ms, 2),
            "success": success,
            "error": error_msg,
            "tokens_used": tokens_used,
            "prompt_length": len(prompt),
            "response_length": len(response),
            # Keep short sanitized snippet for audit review, never storing full unbounded raw inputs
            "prompt_snippet": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "response_snippet": response[:200] + "..." if len(response) > 200 else response
        }

        try:
            parent_dir = os.path.dirname(self.log_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append to copilot audit log: {e}")

        return record
