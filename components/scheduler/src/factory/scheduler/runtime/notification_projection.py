"""Scheduler-owned strict binding builder for the trusted inbox projection.

Builds the exact ``projection`` operation binding and tool arguments for the
Notification ``inbox_publish`` service-only tool. Scheduler owns its own content
digest here so it never imports Notification production code; both sides digest
the identical canonical material via the shared ``mcp_utils`` rail.
"""
from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import protected_canonical_json

_EVENT_TYPE = "scheduler.schedule.auto_paused"
_PRIORITY = "critical"
_TITLE = "Schedule auto-paused"


class AutoPauseProjection(BaseModel):
    """Strict local DTO for one schedule auto-pause notification projection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    schedule_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")
    fire_sequence: int = Field(ge=0)

    @property
    def dedupe_key(self) -> str:
        return f"scheduler-auto-pause:{self.schedule_id}:{self.fire_sequence}"

    @property
    def body(self) -> str:
        return (f"Schedule {self.schedule_id} was auto-paused after five "
                "consecutive failed runs.")

    def _digest(self) -> str:
        canonical = protected_canonical_json({
            "brick": "scheduler", "event_type": _EVENT_TYPE,
            "target_kind": "schedule", "target_id": self.schedule_id,
            "schedule_id": self.schedule_id, "fire_sequence": self.fire_sequence,
            "dedupe_key": self.dedupe_key, "priority": _PRIORITY,
            "title": _TITLE, "body": self.body,
        })
        return hashlib.sha256(canonical).hexdigest()

    def binding(self) -> dict[str, Any]:
        """The exact six-field ``projection`` operation binding."""
        return {
            "tenant_id": self.tenant_id, "owner_id": self.owner_id,
            "event_type": _EVENT_TYPE, "subject_id": self.schedule_id,
            "revision": self.fire_sequence, "payload_digest": self._digest(),
        }

    def arguments(self) -> dict[str, Any]:
        """Tool arguments: the binding plus bounded content and dedupe key."""
        return {
            **self.binding(), "dedupe_key": self.dedupe_key,
            "priority": _PRIORITY, "title": _TITLE, "body": self.body,
        }


__all__ = ["AutoPauseProjection"]
