"""Audit logging for permission decisions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: datetime
    action: str
    resource_type: str
    resource_id: str | None
    decision: str
    reason: str | None
    principal_id: str | None
    tenant_id: str | None
    policy_id: str | None
    rule_id: str | None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "decision": self.decision,
            "reason": self.reason,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
        }


class AuditStore(ABC):
    """Protocol for audit log storage."""

    @abstractmethod
    def log(self, entry: AuditEntry) -> None:
        """Log an audit entry."""
        pass

    @abstractmethod
    def list(
        self,
        action: str | None = None,
        decision: str | None = None,
        principal_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """List audit entries with optional filtering."""
        pass


class InMemoryAuditStore(AuditStore):
    """In-memory audit store for local development."""

    def __init__(self, max_entries: int = 10000):
        self._entries: list[AuditEntry] = []
        self._max_entries = max_entries

    def log(self, entry: AuditEntry) -> None:
        """Log an audit entry."""
        self._entries.append(entry)
        # Trim if over limit
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def list(
        self,
        action: str | None = None,
        decision: str | None = None,
        principal_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """List audit entries with optional filtering."""
        entries = self._entries[:]
        
        if action:
            entries = [e for e in entries if e.action == action]
        if decision:
            entries = [e for e in entries if e.decision == decision]
        if principal_id:
            entries = [e for e in entries if e.principal_id == principal_id]
        
        # Return most recent first
        entries.reverse()
        return entries[:limit]
