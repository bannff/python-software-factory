"""Strict durable Scheduler domain models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScheduleId = Annotated[str, Field(
    min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_-]+$",
)]
Identity = Annotated[str, Field(min_length=1, max_length=256)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScheduleKind(StrEnum):
    INTERVAL = "interval"
    ONE_SHOT = "one_shot"
    CRON = "cron"


class ScheduleState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    AUTO_PAUSED = "auto_paused"
    COMPLETED = "completed"


class FireState(StrEnum):
    CLAIMED = "claimed"
    ENROLLED = "enrolled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleRecord(StrictModel):
    tenant_id: Identity
    owner_id: Identity
    schedule_id: ScheduleId
    origin_session_id: Identity
    origin_thread_id: Identity
    agent_id: ScheduleId
    task: Annotated[str, Field(min_length=1, max_length=100_000)]
    kind: ScheduleKind
    interval_seconds: int | None = Field(default=None, ge=60)
    one_shot_at: datetime | None = None
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="UTC", min_length=1, max_length=128)
    skip_dates: tuple[str, ...] = ()
    strict_schedule: bool = False
    output_schema: Literal["loop-cycle-report-v1"] | None = None
    delivery_mode: Literal["origin", "workflow_loop", "maintenance"] = "origin"
    loop_id: ScheduleId | None = None
    loop_cycle: int | None = Field(default=None, ge=1, le=10_000)
    maintenance_target: Literal["telemetry_retention"] | None = None
    state: ScheduleState = ScheduleState.ACTIVE
    next_fire_at: datetime | None
    last_fire_at: datetime | None = None
    fire_sequence: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def _one_schedule_kind(self) -> "ScheduleRecord":
        values = (self.interval_seconds, self.one_shot_at, self.cron_expression)
        if sum(value is not None for value in values) != 1:
            raise ValueError("exactly one schedule specification is required")
        expected = (
            ScheduleKind.INTERVAL if self.interval_seconds is not None
            else ScheduleKind.ONE_SHOT if self.one_shot_at is not None
            else ScheduleKind.CRON
        )
        if self.kind is not expected:
            raise ValueError("schedule kind does not match its specification")
        loop_values = (self.output_schema, self.loop_id, self.loop_cycle)
        if self.delivery_mode == "workflow_loop":
            if any(value is None for value in loop_values):
                raise ValueError("workflow loop launch binding is incomplete")
            if self.maintenance_target is not None:
                raise ValueError("workflow loop cannot carry maintenance binding")
        elif self.delivery_mode == "maintenance":
            if self.maintenance_target is None:
                raise ValueError("maintenance launch binding is incomplete")
            if any(value is not None for value in loop_values):
                raise ValueError("maintenance cannot carry loop launch binding")
        elif any(value is not None for value in (*loop_values, self.maintenance_target)):
            raise ValueError("origin delivery cannot carry launch binding")
        return self


class FireRecord(StrictModel):
    tenant_id: Identity
    owner_id: Identity
    schedule_id: ScheduleId
    fire_sequence: int = Field(ge=1)
    launch_id: Annotated[str, Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$",
    )]
    state: FireState = FireState.CLAIMED
    workflow_run_id: str | None = Field(default=None, max_length=256)
    created_at: datetime
    updated_at: datetime
    revision: int = Field(ge=1)


__all__ = [
    "FireRecord", "FireState", "ScheduleId", "ScheduleKind",
    "ScheduleRecord", "ScheduleState",
]
