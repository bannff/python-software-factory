"""Strict Migration-owned arguments for protected import targets."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .source_models import SourceKind

_HEX64 = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z0-9][a-z0-9_.-]{0,63}$"


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Identity(_DTO):
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    source_adapter: str = Field(pattern=_NAME)
    source_fingerprint: str = Field(pattern=_HEX64)
    plan_digest: str = Field(pattern=_HEX64)
    source_record_id: str = Field(pattern=_HEX64)
    target_digest: str = Field(pattern=_HEX64)


class MemoryTargetArgs(_Identity):
    kind: Literal["memory"] = "memory"
    subtype: Literal["semantic", "episodic"]
    content: str = Field(min_length=1, max_length=8192)
    key: str = Field(default="", max_length=256)
    tags: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _semantic_key(self) -> "MemoryTargetArgs":
        if self.subtype == "semantic" and not self.key.strip():
            raise ValueError("semantic memory requires a key")
        if any(not tag or len(tag) > 64 for tag in self.tags):
            raise ValueError("memory tag is invalid")
        return self


class LessonTargetArgs(_Identity):
    kind: Literal["lessons"] = "lessons"
    rule: str = Field(min_length=1, max_length=500)
    negative: str | None = Field(default=None, max_length=500)
    category: Literal["tool", "preference", "knowledge"] = "knowledge"
    repo_scope: str = Field(default="", max_length=128)
    evidence: tuple[str, ...] = Field(default=(), max_length=64)


class ScheduleTargetDefinition(_DTO):
    task: str = Field(min_length=1, max_length=100_000)
    agent_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["interval", "one_shot", "cron"]
    interval_seconds: int | None = Field(default=None, ge=60)
    one_shot_at: datetime | None = None
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=128)
    skip_dates: tuple[str, ...] = Field(default=(), max_length=366)
    strict_schedule: bool = False

    @model_validator(mode="after")
    def _shape(self) -> "ScheduleTargetDefinition":
        values = (self.interval_seconds, self.one_shot_at, self.cron_expression)
        expected = {"interval": 0, "one_shot": 1, "cron": 2}[self.kind]
        if values[expected] is None or any(
            value is not None for index, value in enumerate(values) if index != expected
        ):
            raise ValueError("schedule shape is invalid")
        return self


class SchedulerTargetArgs(_Identity):
    kind: Literal["schedules"] = "schedules"
    schedule: ScheduleTargetDefinition


TargetArgs = MemoryTargetArgs | LessonTargetArgs | SchedulerTargetArgs


class PreparedTargetCall(_DTO):
    source_kind: SourceKind
    brick: Literal["memory", "lessons", "scheduler"]
    tool: Literal[
        "memory_import_record", "lessons_import_record", "scheduler_import_record",
    ]
    arguments: TargetArgs

    @model_validator(mode="after")
    def _route_matches(self) -> "PreparedTargetCall":
        expected = {
            MemoryTargetArgs: ("memory", "memory_import_record"),
            LessonTargetArgs: ("lessons", "lessons_import_record"),
            SchedulerTargetArgs: ("scheduler", "scheduler_import_record"),
        }[type(self.arguments)]
        if (self.brick, self.tool) != expected:
            raise ValueError("target route mismatch")
        return self

    def invocation_arguments(self) -> dict:
        """Return strict Python-mode kwargs for the native typed boundary."""
        return self.arguments.model_dump()

    def migration_binding(self) -> dict[str, str]:
        """Project exactly the eight shared service-binding fields."""
        args = self.invocation_arguments()
        fields = (
            "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
            "plan_digest", "kind", "source_record_id", "target_digest",
        )
        return {field: args[field] for field in fields}


__all__ = [
    "LessonTargetArgs", "MemoryTargetArgs", "PreparedTargetCall",
    "ScheduleTargetDefinition", "SchedulerTargetArgs", "TargetArgs",
]
