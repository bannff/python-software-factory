"""Strict contracts for Workflow-driven Migration page execution."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..runtime.source_models import SourceKind

_HEX64 = r"^[0-9a-f]{64}$"
_PLAN = r"^sha256:[0-9a-f]{64}$"


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ApplyPageRequest(DTO):
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    source_adapter: Literal["kirocrew-v1", "companion-x-v1"] = "kirocrew-v1"
    source_fingerprint: str = Field(pattern=_HEX64)
    plan_digest: str = Field(pattern=_PLAN)
    kinds: list[Literal["memory", "lessons", "schedules", "markdown"]] = Field(
        min_length=1, max_length=4)
    page_size: int = Field(default=50, ge=1, le=99)

    @field_validator("kinds")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("execution kinds must be unique")
        return value

    @property
    def source_kinds(self) -> tuple[SourceKind, ...]:
        return tuple(SourceKind(kind) for kind in self.kinds)


class ApplyExecutionInput(DTO):
    request: ApplyPageRequest
    provider_request_digest: str = Field(pattern=_HEX64)
    workflow_run_id: str = Field(min_length=1, max_length=256)
    attempt_id: str = Field(min_length=1, max_length=256)
    revision: int = Field(ge=1)
    engine_id: Literal["migration_import"]
    registration_digest: str = Field(pattern=_HEX64)
    request_digest: str = Field(pattern=_HEX64)


class ApplyExecutionOutput(DTO):
    status: Literal["completed", "partial", "failed"]
    kind: SourceKind
    processed: int = Field(ge=0, le=99)
    imported: int = Field(ge=0, le=99)
    skipped: int = Field(ge=0, le=99)
    failed: int = Field(ge=0, le=99)
    next_offset: int = Field(ge=0)
    retryable: bool
    error: Literal[
        "", "migration_plan_unavailable", "migration_receipt_conflict",
        "migration_target_failed", "migration_target_unavailable",
        "migration_cursor_conflict",
    ] = ""


__all__ = ["ApplyExecutionInput", "ApplyExecutionOutput", "ApplyPageRequest", "DTO"]
