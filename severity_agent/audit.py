"""
ICU Guard v5.0 — Regulatory Audit & Decision Provenance Logger
=============================================================
Provides FDA SaMD (Software as a Medical Device) / EU MDR-compliant audit logging:
1. Cryptographically Verifiable Hash-Chained Audit Ledger (SHA-256)
2. Immutable Snapshot of Inputs, Model Predictions, and Decision Overrides
3. Safety Override & Absolute Red Flag Provenance Tracking
4. Tamper-Evident Record Verification for Clinical Governance & Regulatory Inspections
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
import datetime
import hashlib
import json
import os
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuditRecord:
    """Tamper-evident audit entry for a single clinical inference."""
    record_id: str
    timestamp_utc: str
    patient_id: str
    input_hash: str
    model_version: str
    probabilities: Dict[str, float]
    final_tier: str
    escalation_occurred: bool
    escalation_reasons: List[str]
    active_red_flags: List[str]
    validation_status: str
    prev_record_hash: str
    record_hash: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class RegulatoryAuditLogger:
    """Maintains a secure, hash-chained regulatory audit ledger in local storage."""

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or "e:/eicu_v2_0_1.sqlite3/severity_agent/audit_ledger.jsonl"
        self._last_hash = "0" * 64
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            rec = json.loads(line)
                            if "record_hash" in rec:
                                self._last_hash = rec["record_hash"]
            except Exception:
                pass

    def log_assessment(
        self,
        patient_id: Any,
        inputs: Dict[str, Any],
        probabilities: Dict[str, float],
        severity_tier: str,
        escalation_occurred: bool,
        escalation_reasons: List[str],
        active_red_flags: List[str],
        validation_status: str,
        model_version: str = "5.0.0"
    ) -> AuditRecord:
        """Create and commit a hash-chained audit record."""
        rec_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Compute input payload hash (SHA-256)
        input_str = json.dumps(inputs, sort_keys=True, default=str)
        input_hash = hashlib.sha256(input_str.encode('utf-8')).hexdigest()

        # Build preliminary record content for chaining
        content_dict = {
            "record_id": rec_id,
            "timestamp_utc": ts,
            "patient_id": str(patient_id),
            "input_hash": input_hash,
            "model_version": model_version,
            "probabilities": probabilities,
            "final_tier": severity_tier,
            "escalation_occurred": escalation_occurred,
            "escalation_reasons": escalation_reasons,
            "active_red_flags": active_red_flags,
            "validation_status": validation_status,
            "prev_record_hash": self._last_hash
        }

        # Generate cryptographic block hash
        content_str = json.dumps(content_dict, sort_keys=True)
        record_hash = hashlib.sha256(content_str.encode('utf-8')).hexdigest()

        record = AuditRecord(
            record_id=rec_id,
            timestamp_utc=ts,
            patient_id=str(patient_id),
            input_hash=input_hash,
            model_version=model_version,
            probabilities=probabilities,
            final_tier=severity_tier,
            escalation_occurred=escalation_occurred,
            escalation_reasons=escalation_reasons,
            active_red_flags=active_red_flags,
            validation_status=validation_status,
            prev_record_hash=self._last_hash,
            record_hash=record_hash
        )

        self._last_hash = record_hash

        # Persist entry to append-only jsonl log
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist audit record: {e}")

        return record

    def verify_ledger(self, ledger_file: Optional[str] = None) -> Tuple[bool, int, str]:
        """Verify the cryptographic hash-chain integrity of the audit log."""
        target = ledger_file or self.log_path
        if not os.path.exists(target):
            return True, 0, "No audit log found (clean start)."

        prev = "0" * 64
        count = 0
        with open(target, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip(): continue
                rec = json.loads(line)
                if rec['prev_record_hash'] != prev:
                    return False, count, f"Hash chain broken at record {line_no} (expected prev {prev}, found {rec['prev_record_hash']})"
                
                # Recompute hash
                check_dict = {
                    "record_id": rec['record_id'],
                    "timestamp_utc": rec['timestamp_utc'],
                    "patient_id": rec['patient_id'],
                    "input_hash": rec['input_hash'],
                    "model_version": rec['model_version'],
                    "probabilities": rec['probabilities'],
                    "final_tier": rec['final_tier'],
                    "escalation_occurred": rec['escalation_occurred'],
                    "escalation_reasons": rec['escalation_reasons'],
                    "active_red_flags": rec['active_red_flags'],
                    "validation_status": rec['validation_status'],
                    "prev_record_hash": rec['prev_record_hash']
                }
                calc_hash = hashlib.sha256(json.dumps(check_dict, sort_keys=True).encode('utf-8')).hexdigest()
                if calc_hash != rec['record_hash']:
                    return False, count, f"Data tampering detected at record {line_no} (hash mismatch)."
                
                prev = rec['record_hash']
                count += 1

        return True, count, f"Cryptographic integrity verified across {count} audit records."
