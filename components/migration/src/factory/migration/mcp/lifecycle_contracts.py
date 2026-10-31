"""Strict public contracts for Migration start and progress reads."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..runtime.source_models import SourceKind


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MigrationStartInput(DTO):
    plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source: Literal["kirocrew-v1", "companion-x-v1"] = "kirocrew-v1"
    kinds: list[Literal["memory", "lessons", "schedules", "markdown"]] = Field(
        min_length=1, max_length=4)

    @field_validator("kinds")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("migration kinds must be unique")
        return value


class MigrationStartOutput(DTO):
    run_id: str = Field(min_length=1, max_length=256)
    status: str = Field(min_length=1, max_length=32)


class MigrationGetInput(DTO):
    run_id: str = Field(min_length=1, max_length=256)


class KindProgress(DTO):
    kind: SourceKind
    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
    cursor: int = Field(ge=0)


class MigrationGetOutput(DTO):
    run_id: str
    status: str
    progress: tuple[KindProgress, ...]
    terminal_reason: Literal[
        "", "completed", "cancelled", "workflow_failed", "continuation_exhausted",
    ] = ""


__all__ = [
    "KindProgress", "MigrationGetInput", "MigrationGetOutput",
    "MigrationStartInput", "MigrationStartOutput",
]
