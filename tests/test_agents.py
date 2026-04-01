"""Tests for agents and audit trail."""
from __future__ import annotations
import json
from src.audit.trail import AuditTrail
from src.models.schemas import AgentName


class TestAuditTrailSetup:
    def test_creation(self, audit_trail):
        assert audit_trail.run_id == "test-fixture"
        assert audit_trail.entries == []

    def test_chain_integrity(self, audit_trail):
        audit_trail.log_action(
            agent=AgentName.SUPERVISOR, action="test",
            inputs={"x": 1}, outputs={"y": 2},
            model_version="v1", prompt_template="p",
        )
        assert audit_trail.verify_chain() is True

    def test_chain_detects_tampering(self, audit_trail):
        audit_trail.log_action(
            agent=AgentName.SUPERVISOR, action="a1",
            inputs={}, outputs={}, model_version="v1", prompt_template="p1",
        )
        audit_trail.log_action(
            agent=AgentName.QUERY_GENERATION, action="a2",
            inputs={}, outputs={}, model_version="v1", prompt_template="p2",
        )
        lines = audit_trail.log_file.read_text().strip().split("\n")
        record = json.loads(lines[0])
        record["action"] = "TAMPERED"
        lines[0] = json.dumps(record)
        audit_trail.log_file.write_text("\n".join(lines) + "\n")
        assert audit_trail.verify_chain() is False

    def test_approve_entry_persists(self, audit_trail):
        """[FIX C3] Verify approval creates a new JSONL record."""
        entry = audit_trail.log_action(
            agent=AgentName.QUERY_GENERATION, action="detect",
            inputs={}, outputs={}, model_version="v1", prompt_template="p",
        )
        assert audit_trail.approve_entry(entry.entry_id, "dr_smith") is True
        # Should have 2 entries: original + approval amendment
        assert len(audit_trail.entries) == 2
        assert audit_trail.entries[1].action == "approval_amendment"
        # JSONL should have 2 lines
        lines = audit_trail.log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        assert audit_trail.verify_chain() is True
