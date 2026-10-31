"""Strict typed lesson records and lifecycle vocabulary."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LessonCategory(StrEnum):
    TOOL = "tool"
    PREFERENCE = "preference"
    KNOWLEDGE = "knowledge"


class LessonScope(StrEnum):
    GLOBAL = "global"
    PERSONA = "persona"


class LessonSource(StrEnum):
    USER_EXPLICIT = "user_explicit"
    FEEDBACK = "feedback"
    OUTCOME = "outcome"
    IMPORT = "import"


class LessonStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class LessonRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    lesson_id: str = Field(pattern=r"^les_[0-9a-f]{32}$")
    identity_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule: str = Field(min_length=1, max_length=500)
    negative: str | None = Field(default=None, max_length=500)
    category: LessonCategory
    scope: LessonScope
    scope_id: str | None = Field(default=None, max_length=128)
    source: LessonSource
    source_ref: str | None = Field(default=None, max_length=256)
    evidence: tuple[str, ...] = Field(default=(), max_length=64)
    confidence: float = Field(ge=0.0, le=1.0)
    status: LessonStatus
    superseded_ids: tuple[str, ...] = Field(default=(), max_length=64)
    memory_id: str | None = Field(default=None, max_length=256)
    memory_revision: int | None = Field(default=None, ge=1)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("rule", "negative")
    @classmethod
    def _nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("lesson text must not be blank")
        return value

    @field_validator("evidence")
    @classmethod
    def _bounded_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 1024 for item in value):
            raise ValueError("lesson evidence item is invalid")
        return value

    @model_validator(mode="after")
    def _scope_and_projection(self) -> "LessonRecord":
        if (self.scope is LessonScope.PERSONA) != (self.scope_id is not None):
            raise ValueError("persona scope requires exactly one scope_id")
        if (self.memory_id is None) != (self.memory_revision is None):
            raise ValueError("Memory projection binding is incomplete")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("lesson timestamps must be timezone-aware")
        return self




class RecallLesson(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    lesson_id: str = Field(pattern=r"^les_[0-9a-f]{32}$")
    rule: str = Field(min_length=1, max_length=500)
    negative: str | None = Field(default=None, max_length=500)
    scope: LessonScope
    scope_id: str | None = Field(default=None, max_length=128)
class LessonWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    outcome: Literal["inserted", "enriched", "unchanged", "deduped", "refused"]
    reason: str = Field(min_length=1, max_length=128)
    lesson: LessonRecord | None = None
    superseded_ids: tuple[str, ...] = ()


__all__ = ["LessonCategory", "LessonRecord", "LessonScope", "LessonSource",
           "LessonStatus", "LessonWriteResult", "RecallLesson"]
