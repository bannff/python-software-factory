"""Agent runner models — value objects for the supervised runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RunnerStatus(str, Enum):
    """Agent runner lifecycle status."""

    PARKED = "parked"
    ACTIVE = "active"
    ERROR = "error"


@dataclass(frozen=True)
class InboxMessage:
    """A message enqueued for a named agent."""

    agent_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentRunnerState:
    """Persisted state for a single named agent runner."""

    agent_id: str
    status: RunnerStatus = RunnerStatus.PARKED
    auto_wake_at: datetime | None = None
    session_id: str | None = None
    turn_count: int = 0
    last_active_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "auto_wake_at": self.auto_wake_at.isoformat() if self.auto_wake_at else None,
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRunnerState":
        """Reconstruct state from a serialized dict (inverse of to_dict)."""
        return cls(
            agent_id=data["agent_id"],
            status=RunnerStatus(data["status"]),
            auto_wake_at=(
                datetime.fromisoformat(data["auto_wake_at"])
                if data.get("auto_wake_at")
                else None
            ),
            session_id=data.get("session_id"),
            turn_count=data.get("turn_count", 0),
            last_active_at=(
                datetime.fromisoformat(data["last_active_at"])
                if data.get("last_active_at")
                else None
            ),
        )
