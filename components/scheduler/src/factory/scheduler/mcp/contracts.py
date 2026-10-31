"""Strict Scheduler MCP ingress and egress DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import WireDatetime

from ..runtime.models import FireRecord, ScheduleRecord


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EnvelopeInput(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    thread_id: str | None = None


class ScheduleRefInput(DTO):
    schedule_id: str
    envelope: EnvelopeInput | None = None


class ListSchedulesInput(DTO):
    envelope: EnvelopeInput | None = None


class FireRefInput(ScheduleRefInput):
    fire_sequence: int = Field(ge=1)


class AddScheduleInput(DTO):
    agent_id: str = Field(min_length=1, max_length=96)
    task: str = Field(min_length=1, max_length=100_000)
    kind: Literal["interval", "one_shot", "cron"]
    interval_seconds: int | None = None
    one_shot_at: WireDatetime | None = None
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=128)
    skip_dates: tuple[str, ...] = ()
    strict_schedule: bool = False
    output_schema: Literal["loop-cycle-report-v1"] | None = None
    delivery_mode: Literal["origin", "workflow_loop"] = "origin"
    loop_id: str | None = Field(default=None, max_length=80)
    loop_cycle: int | None = Field(default=None, ge=1, le=10_000)
    schedule_id: str | None = Field(default=None, max_length=96)
    envelope: EnvelopeInput | None = None


class RevisionInput(ScheduleRefInput):
    expected_revision: int = Field(ge=1)


class ScheduleOutput(DTO):
    schedule: ScheduleRecord


class SchedulesOutput(DTO):
    schedules: list[ScheduleRecord]


class FireOutput(DTO):
    fire: FireRecord


class RemovedOutput(DTO):
    removed: bool
    schedule_id: str


__all__ = [
    "AddScheduleInput", "FireOutput", "FireRefInput", "ListSchedulesInput",
    "RemovedOutput",
    "RevisionInput", "ScheduleOutput", "ScheduleRefInput", "SchedulesOutput",
]
