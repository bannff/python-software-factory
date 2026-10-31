"""Tests for audit logging."""
from __future__ import annotations

from pathlib import Path

import yaml

from factory.permissions.runtime.envelope import Envelope
from factory.permissions.runtime.runtime import PermissionsRuntime
from factory.permissions.runtime.audit import InMemoryAuditStore


def _write_min_config(cfg: Path) -> None:
    (cfg / "policies").mkdir(parents=True, exist_ok=True)
    (cfg / "settings.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "service_name": "test",
        "backend": "filesystem",
        "authoring": {"enabled": False},
        "policy_store": {"policies_subdir": "policies"},
    }))


class TestAuditLogging:
    """Test audit logging functionality."""

    def test_evaluate_logs_decision(self, tmp_path: Path) -> None:
        """Evaluate should log the decision."""
        _write_min_config(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        audit_store = InMemoryAuditStore()
        runtime.set_audit_store(audit_store)
        
        runtime.evaluate(
            action="read",
            resource={"type": "document", "id": "doc-1"},
            context={},
            envelope=Envelope(principal_id="user-123"),
        )
        
        entries = audit_store.list()
        assert len(entries) == 1
        assert entries[0].action == "read"
        assert entries[0].decision == "deny"
        assert entries[0].principal_id == "user-123"

    def test_batch_evaluate_logs_all(self, tmp_path: Path) -> None:
        """Batch evaluate should log all decisions."""
        _write_min_config(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        audit_store = InMemoryAuditStore()
        runtime.set_audit_store(audit_store)
        
        runtime.batch_evaluate(
            requests=[
                {"action": "read", "resource": {"type": "doc", "id": "1"}},
                {"action": "write", "resource": {"type": "doc", "id": "2"}},
            ],
            envelope=Envelope(),
        )
        
        entries = audit_store.list()
        assert len(entries) == 2

    def test_list_audit_log_with_filter(self, tmp_path: Path) -> None:
        """Should filter audit log by action."""
        _write_min_config(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        audit_store = InMemoryAuditStore()
        runtime.set_audit_store(audit_store)
        
        runtime.evaluate(action="read", resource={"type": "doc"}, context={}, envelope=Envelope())
        runtime.evaluate(action="write", resource={"type": "doc"}, context={}, envelope=Envelope())
        runtime.evaluate(action="read", resource={"type": "doc"}, context={}, envelope=Envelope())
        
        read_entries = audit_store.list(action="read")
        assert len(read_entries) == 2
        
        write_entries = audit_store.list(action="write")
        assert len(write_entries) == 1

    def test_audit_entry_has_timestamp(self, tmp_path: Path) -> None:
        """Audit entries should have timestamps."""
        _write_min_config(tmp_path)
        runtime = PermissionsRuntime.from_config_dir(tmp_path)
        audit_store = InMemoryAuditStore()
        runtime.set_audit_store(audit_store)
        
        runtime.evaluate(action="read", resource={"type": "doc"}, context={}, envelope=Envelope())
        
        entries = audit_store.list()
        assert entries[0].timestamp is not None
