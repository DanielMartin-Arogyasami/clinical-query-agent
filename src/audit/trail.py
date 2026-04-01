"""
Immutable audit trail — 21 CFR Part 11 compliance.
[FIX C3] approve_entry now persists amendment record to JSONL.
[FIX M2] Uses datetime.now(timezone.utc).
[FIX M3] Thread-safe file writes via threading.Lock.
"""
from __future__ import annotations
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import structlog
from config.settings import settings
from src.models.schemas import AgentName, ApprovalStatus, AuditEntry

logger = structlog.get_logger(__name__)


class AuditTrail:
    """Append-only, hash-chained audit trail."""

    def __init__(self, run_id: str, log_dir: str | None = None):
        self.run_id = run_id
        self.log_dir = Path(log_dir or settings.audit_log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"audit_{run_id}.jsonl"
        self.entries: list[AuditEntry] = []
        self._prev_hash: str = "GENESIS"
        self._write_lock = threading.Lock()  # FIX M3

    @staticmethod
    def compute_hash(data: Any) -> str:
        serialised = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def log_action(
        self,
        agent: AgentName,
        action: str,
        inputs: Any,
        outputs: Any,
        model_version: str,
        prompt_template: str,
        retrieval_citations: list[str] | None = None,
        confidence: float | None = None,
        human_approval: ApprovalStatus = ApprovalStatus.PENDING,
        human_approver: str | None = None,
        notes: str | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            agent=agent,
            action=action,
            inputs_hash=self.compute_hash(inputs),
            outputs_hash=self.compute_hash(outputs),
            model_version=model_version,
            prompt_template_hash=self.compute_hash(prompt_template),
            retrieval_citations=retrieval_citations or [],
            confidence=confidence,
            human_approval=human_approval,
            human_approver=human_approver,
            notes=notes,
        )
        self.entries.append(entry)
        self._append_to_file(entry)
        logger.info("audit.logged", agent=agent.value, action=action, entry_id=entry.entry_id)
        return entry

    def _append_to_file(self, entry: AuditEntry) -> None:
        """Thread-safe append with hash chain."""
        with self._write_lock:  # FIX M3
            record = entry.model_dump(mode="json")
            record["_chain_hash"] = self.compute_hash({"prev": self._prev_hash, "entry": record})
            self._prev_hash = record["_chain_hash"]
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")

    def verify_chain(self) -> bool:
        if not self.log_file.exists():
            return True
        prev_hash = "GENESIS"
        with open(self.log_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                record = json.loads(line)
                stored = record.pop("_chain_hash")
                expected = self.compute_hash({"prev": prev_hash, "entry": record})
                if stored != expected:
                    logger.error("audit.chain_broken", line=line_num)
                    return False
                prev_hash = stored
        return True

    def get_pending_approvals(self) -> list[AuditEntry]:
        return [e for e in self.entries if e.human_approval == ApprovalStatus.PENDING]

    def approve_entry(self, entry_id: str, approver: str) -> bool:
        """Record human approval — persists amendment to JSONL. [FIX C3]"""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.human_approval = ApprovalStatus.APPROVED
                entry.human_approver = approver
                # Persist amendment as a new audit record
                self.log_action(
                    agent=entry.agent,
                    action="approval_amendment",
                    inputs={"amended_entry_id": entry_id},
                    outputs={"status": "approved", "approver": approver},
                    model_version="N/A",
                    prompt_template="N/A",
                    human_approval=ApprovalStatus.APPROVED,
                    human_approver=approver,
                    notes=f"Human approval for entry {entry_id}",
                )
                return True
        return False

    def export_summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_entries": len(self.entries),
            "by_agent": {a.value: sum(1 for e in self.entries if e.agent == a) for a in AgentName},
            "pending_approvals": len(self.get_pending_approvals()),
            "chain_valid": self.verify_chain(),
            "log_file": str(self.log_file),
        }
