"""Strict transport DTOs for the protected Memory import tool (M7 slice 2)."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import DTO

_HEX64 = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z0-9][a-z0-9_.-]{0,63}$"

_Tag = Annotated[str, Field(min_length=1, max_length=64)]


class MemoryImportInput(DTO):
    """Exactly the eight MigrationImportBinding identity fields plus the
    bounded target-native payload. ``extra='forbid'`` (via ``DTO``) rejects
    any additional field."""

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    source_adapter: str = Field(pattern=_NAME)
    source_fingerprint: str = Field(pattern=_HEX64)
    plan_digest: str = Field(pattern=_HEX64)
    kind: str = Field(pattern=_NAME)
    source_record_id: str = Field(pattern=_HEX64)
    target_digest: str = Field(pattern=_HEX64)
    subtype: Literal["semantic", "episodic"]
    content: str = Field(min_length=1, max_length=8192)
    key: str = Field(default="", max_length=256)
    tags: list[_Tag] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _key_matches_subtype(self) -> "MemoryImportInput":
        if self.subtype == "semantic" and not self.key.strip():
            raise ValueError("semantic memory requires a key")
        return self


class MemoryImportOutput(DTO):
    imported: bool = False
    outcome: str | None = None
    memory_id: str | None = None
    error: str | None = None
