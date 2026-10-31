"""Strict typed Lessons MCP contracts."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..runtime.models import LessonRecord, LessonWriteResult


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EnvelopeInput(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None


class AddLessonInput(DTO):
    rule: str = Field(min_length=1, max_length=500)
    negative: str | None = Field(default=None, max_length=500)
    category: Literal["tool", "preference", "knowledge"] = "knowledge"
    scope: Literal["global", "persona"] = "global"
    scope_id: str | None = Field(default=None, max_length=128)
    evidence: tuple[str, ...] = Field(default=(), max_length=64)
    envelope: EnvelopeInput | None = None

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 1024 for item in value):
            raise ValueError("lesson evidence item is invalid")
        return value

    @model_validator(mode="after")
    def _scope(self) -> "AddLessonInput":
        if (self.scope == "persona") != (self.scope_id is not None):
            raise ValueError("persona scope requires exactly one scope_id")
        return self


class LessonRefInput(DTO):
    lesson_id: str = Field(pattern=r"^les_[0-9a-f]{32}$")
    envelope: EnvelopeInput | None = None




class ProposalLessonInput(DTO):
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    source_ref: str = Field(min_length=1, max_length=256)
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: Literal["feedback", "outcome"]
    rule: str = Field(min_length=1, max_length=500)
    negative: str | None = Field(default=None, max_length=500)
    category: Literal["tool", "preference", "knowledge"] = "knowledge"
    scope: Literal["global", "persona"] = "global"
    scope_id: str | None = Field(default=None, max_length=128)
    evidence: tuple[str, ...] = Field(default=(), max_length=64)
    confidence: float = Field(ge=0.0, le=1.0)


class ImportLessonInput(DTO):
    """One trusted Migration→Lessons import of a user-authored lesson.

    Carries the eight flat MigrationImportBinding fields (matched at the
    service boundary) plus the bounded lesson content. ``kind`` is fixed to
    ``lessons`` and ``target_digest`` is recomputed before any write.
    """

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    source_adapter: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["lessons"]
    source_record_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule: str = Field(min_length=1, max_length=500)
    negative: str | None = Field(default=None, max_length=500)
    category: Literal["tool", "preference", "knowledge"] = "knowledge"
    repo_scope: str = Field(default="", max_length=128)
    evidence: tuple[str, ...] = Field(default=(), max_length=64)

    @field_validator("rule", "negative")
    @classmethod
    def _nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("lesson text must not be blank")
        return value

    @field_validator("repo_scope")
    @classmethod
    def _repo_scope(cls, value: str) -> str:
        if value and not value.strip():
            raise ValueError("repo_scope must not be blank")
        return value

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() or len(item) > 1024 for item in value):
            raise ValueError("lesson evidence item is invalid")
        return value


class ImportLessonOutput(DTO):
    imported: bool
    replayed: bool
    outcome: Literal["inserted", "enriched", "unchanged", "deduped", "refused"]
    lesson: LessonRecord


class LessonRevisionInput(LessonRefInput):
    expected_revision: int = Field(ge=1)

class ListLessonsInput(DTO):
    limit: int = Field(default=100, ge=1, le=1000)
    envelope: EnvelopeInput | None = None


class LessonOutput(DTO):
    lesson: LessonRecord


class LessonsOutput(DTO):
    lessons: list[LessonRecord]


class LessonWriteOutput(DTO):
    result: LessonWriteResult


class RemovedOutput(DTO):
    lesson_id: str
    removed: bool


class RecallInput(DTO):
    query: str = Field(min_length=1, max_length=16_384)
    persona_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    limit: int = Field(default=8, ge=1, le=16)
    envelope: EnvelopeInput | None = None


class RecallItem(DTO):
    lesson_id: str
    rule: str
    negative: str | None = None
    scope: Literal["global", "persona"]
    scope_id: str | None = None


class RecallOutput(DTO):
    lessons: list[RecallItem]


__all__ = ["AddLessonInput", "DTO", "ImportLessonInput", "ImportLessonOutput",
           "LessonOutput", "LessonRefInput",
           "LessonRevisionInput", "LessonsOutput", "LessonWriteOutput",
           "ListLessonsInput", "ProposalLessonInput", "RecallInput",
           "RecallItem", "RecallOutput", "RemovedOutput"]
