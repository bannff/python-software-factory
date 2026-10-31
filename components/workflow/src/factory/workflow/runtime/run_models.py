"""Immutable Workflow run and event records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .envelope import FrozenEnvelope

RunStatus = Literal["pending", "running", "waiting", "succeeded", "failed", "cancelled"]


class RunRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    run_key: str | None = None
    workflow_id: str
    workflow_version: int
    workflow_version_id: str | None = None
    run_execution_id: str | None = None
    revision: int = 0
    status: RunStatus
    current_step_id: str | None = None
    waiting_for_event_type: str | None = None
    last_event_id: int = 0
    started_at: datetime
    updated_at: datetime
    input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    tenant_id: str | None = None
    initiation_envelope: FrozenEnvelope = Field(default_factory=FrozenEnvelope)


class EventRecord(BaseModel):
    id: int
    run_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
