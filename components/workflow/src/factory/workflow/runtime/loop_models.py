"""Workflow-owned durable goal and monitor loop policy records."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .envelope import FrozenEnvelope

_ID = r"^[a-z0-9][a-z0-9_-]{0,127}$"
_LOOP_ID = r"^[a-z0-9][a-z0-9_-]{0,79}$"


class LoopKind(StrEnum):
    GOAL = "goal"
    MONITOR = "monitor"


class LoopState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    STOPPED = "stopped"
    EXHAUSTED = "exhausted"
    FAILED = "failed"


class CycleState(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SETTLED = "settled"


class CycleDisposition(StrEnum):
    CONTINUE = "continue"
    SUCCESS = "success"
    BLOCKED = "blocked"
    FAILED = "failed"


class LoopRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    loop_id: str = Field(pattern=_LOOP_ID)
    origin_session_id: str = Field(pattern=_ID)
    origin_thread_id: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(pattern=_ID)
    kind: LoopKind
    objective: str = Field(min_length=1, max_length=16_384)
    cycle_instructions: str = Field(min_length=1, max_length=16_384)
    interval_seconds: int = Field(ge=15, le=86_400)
    max_cycles: int = Field(default=24, ge=0, le=10_000)
    runtime_deadline: datetime | None = None
    project_root: str = Field(min_length=1, max_length=4096)
    project_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: LoopState = LoopState.ACTIVE
    terminal_reason: str | None = Field(default=None, max_length=128)
    next_cycle: int = Field(default=1, ge=1)
    last_settled_cycle: int = Field(default=0, ge=0)
    blocker_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    blocker_projected: bool = False
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    initiation_envelope: FrozenEnvelope

    @field_validator("runtime_deadline", "created_at", "updated_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("loop timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _sequence(self) -> "LoopRecord":
        if self.next_cycle != self.last_settled_cycle + 1:
            raise ValueError("loop cycle sequence must be contiguous")
        if self.initiation_envelope.tenant_id != self.tenant_id:
            raise ValueError("loop tenant binding mismatch")
        if self.initiation_envelope.principal_id != self.owner_id:
            raise ValueError("loop owner binding mismatch")
        if self.initiation_envelope.session_id != self.origin_thread_id:
            raise ValueError("loop origin-thread binding mismatch")
        return self


class LoopCycleReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    disposition: Literal["continue", "success", "blocked"]
    summary: str = Field(min_length=1, max_length=32_768)
    blocker: str | None = Field(default=None, max_length=16_384)
    evidence: list[str] = Field(default_factory=list, max_length=64)



class LoopCycleRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    loop_id: str = Field(pattern=_LOOP_ID)
    cycle: int = Field(ge=1)
    schedule_id: str = Field(pattern=_ID)
    scheduled_for: datetime
    state: CycleState = CycleState.PENDING
    workflow_run_id: str | None = Field(default=None, min_length=1, max_length=256)
    disposition: CycleDisposition | None = None
    summary: str | None = Field(default=None, max_length=32_768)
    blocker_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _settled(self) -> "LoopCycleRecord":
        if (self.scheduled_for.tzinfo is None or self.created_at.tzinfo is None
                or self.updated_at.tzinfo is None):
            raise ValueError("loop cycle timestamps must be timezone-aware")
        if (self.state is CycleState.SETTLED) != (self.disposition is not None):
            raise ValueError("settled cycles require exactly one disposition")
        return self


TERMINAL_LOOP_STATES = frozenset({
    LoopState.SUCCEEDED, LoopState.BLOCKED, LoopState.STOPPED,
    LoopState.EXHAUSTED, LoopState.FAILED,
})

__all__ = ["CycleDisposition", "CycleState", "LoopCycleRecord", "LoopCycleReport",
           "LoopKind",
           "LoopRecord", "LoopState", "TERMINAL_LOOP_STATES"]
