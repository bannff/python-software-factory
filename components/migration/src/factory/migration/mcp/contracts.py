"""Strict Migration MCP contracts."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..runtime.receipt_models import CommitStatus
from ..runtime.source_models import (
    Diagnostic, KindReport, PreviewSample, SourceKind, StagedFile,
)


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PreviewInput(DTO):
    source: Literal["kirocrew-v1"] = "kirocrew-v1"
    kinds: list[Literal["memory", "lessons", "schedules", "markdown"]] = Field(
        default_factory=lambda: [kind.value for kind in SourceKind],
        min_length=1, max_length=4)

    @field_validator("kinds")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("migration kinds must be unique")
        return value


class PreviewOutput(DTO):
    source: Literal["kirocrew-v1"] = "kirocrew-v1"
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: CommitStatus
    files: tuple[StagedFile, ...]
    reports: tuple[KindReport, ...]
    samples: tuple[PreviewSample, ...] = Field(max_length=12)
    snapshot_diagnostics: tuple[Diagnostic, ...] = Field(max_length=200)


__all__ = ["DTO", "PreviewInput", "PreviewOutput"]
