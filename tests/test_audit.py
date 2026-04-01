"""Tests for audit trail integrity."""
from __future__ import annotations
from src.audit.trail import AuditTrail
from src.models.schemas import AgentName


class TestAuditTrail:
    def test_hash_deterministic(self):
        assert AuditTrail.compute_hash({"k": "v"}) == AuditTrail.compute_hash({"k": "v"})

    def test_hash_different(self):
        assert AuditTrail.compute_hash({"k": "v1"}) != AuditTrail.compute_hash({"k": "v2"})

    def test_10_entry_chain(self, tmp_path):
        audit = AuditTrail(run_id="chain-10", log_dir=str(tmp_path))
        for i in range(10):
            audit.log_action(
                agent=AgentName.SUPERVISOR, action=f"a{i}",
                inputs={"i": i}, outputs={}, model_version="v1", prompt_template="p",
            )
        assert len(audit.entries) == 10
        assert audit.verify_chain() is True

    def test_export_summary(self, tmp_path):
        audit = AuditTrail(run_id="summary", log_dir=str(tmp_path))
        audit.log_action(
            agent=AgentName.QUERY_GENERATION, action="x",
            inputs={}, outputs={}, model_version="v1", prompt_template="p",
        )
        s = audit.export_summary()
        assert s["total_entries"] == 1
        assert s["chain_valid"] is True
