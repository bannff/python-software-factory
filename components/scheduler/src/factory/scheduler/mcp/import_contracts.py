"""Strict Scheduler migration-import ingress and egress DTOs.

The nested schedule definition is a closed, safe subset of the durable
schedule: it carries only the timing and delivery-neutral fields a migration
may set. ``extra="forbid"`` on every model rejects unsafe carriers such as
``approval_mode``/``script``/``command``/``env``/``channel`` and any runtime
result/error field before validation or effects.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.models import ScheduleRecord

_SHA256 = r"^[0-9a-f]{64}$"


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ImportScheduleDefinition(DTO):
    """The safe, target-owned schedule the migration is allowed to set."""

    task: str = Field(min_length=1, max_length=100_000)
    agent_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["interval", "one_shot", "cron"]
    interval_seconds: int | None = Field(default=None, ge=60)
    one_shot_at: datetime | None = None
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=128)
    skip_dates: tuple[str, ...] = ()
    strict_schedule: bool = False


class SchedulerImportInput(DTO):
    """One protected Migration-to-Scheduler import write.

    The eight flat identity fields form the exact ``migration_import`` binding
    the service-only boundary matches; ``kind`` is fixed to ``schedules``.
    """

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    source_adapter: str = Field(min_length=1, max_length=64)
    source_fingerprint: str = Field(pattern=_SHA256)
    plan_digest: str = Field(pattern=_SHA256)
    kind: Literal["schedules"]
    source_record_id: str = Field(pattern=_SHA256)
    target_digest: str = Field(pattern=_SHA256)
    schedule: ImportScheduleDefinition


class SchedulerImportOutput(DTO):
    imported: bool
    replayed: bool
    schedule: ScheduleRecord


__all__ = [
    "ImportScheduleDefinition", "SchedulerImportInput", "SchedulerImportOutput",
]
