"""Strict artifact records and save outcomes."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CONTENT_BYTES = 1_048_576
ActorKind: TypeAlias = Literal["agent", "human"]
ArtifactMutationEventType: TypeAlias = Literal["updated", "reverted"]


def validate_content(value: str) -> str:
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("artifact content must be UTF-8") from exc
    if size > MAX_CONTENT_BYTES:
        raise ValueError("artifact content exceeds byte limit")
    return value


def validate_folder_name(value: str) -> str:
    if not value.strip() or "/" in value:
        raise ValueError("folder name is invalid")
    return value.strip()


class ArtifactKind(StrEnum):
    WIDGET = "widget"
    HTML = "html"
    MARKDOWN = "markdown"
    SVG = "svg"
    JSON = "json"
    TEXT = "text"


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    kind: ArtifactKind
    tags: tuple[str, ...] = Field(default=(), max_length=16)
    folder_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: int = Field(default=1, ge=1)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("artifact name must not be blank")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(
            not item.strip() or len(item) > 64 for item in value
        ):
            raise ValueError("artifact tags are invalid")
        return value

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return validate_content(value)

    @model_validator(mode="after")
    def _timestamps(self) -> "ArtifactRecord":
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("artifact timestamps must be timezone-aware")
        return self


class ArtifactVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    tenant_id: str
    owner_id: str
    slug: str
    version: int = Field(ge=1)
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: ArtifactKind
    actor_kind: ActorKind
    event_type: Literal["created", "updated", "reverted"]
    created_at: datetime


class ArtifactWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    outcome: Literal["created", "matched", "updated", "reverted"]
    artifact: ArtifactRecord


class ArtifactFolder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    parent_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    name: str = Field(min_length=1, max_length=100)
    position: int = Field(ge=0)
    revision: int = Field(ge=1)
    path: str = Field(min_length=1, max_length=2_019)
    depth: int = Field(ge=1, le=20)
    item_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime

    @field_validator("name")
    @classmethod
    def _folder_name(cls, value: str) -> str:
        return validate_folder_name(value)


class PublicationNotice(BaseModel):
    """Result of publishing an artifact to a provider-neutral publish target.

    ``provider`` names the ``PublishProvider`` adapter used, never a token or
    URL by value. ``external_ref`` is whatever the provider returns to later
    ``refresh()`` the notice (e.g. a remote id) — opaque to this brick.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
    provider: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    external_ref: str = Field(min_length=1, max_length=512)
    status: Literal["published", "unavailable", "removed"]
    detail: str = Field(default="", max_length=2_000)
    revision: int = Field(ge=1)
    published_at: datetime
    last_checked_at: datetime

    @model_validator(mode="after")
    def _timestamps(self) -> "PublicationNotice":
        if self.published_at.tzinfo is None or self.last_checked_at.tzinfo is None:
            raise ValueError("publication notice timestamps must be timezone-aware")
        return self


class ArtifactComment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
    root_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    parent_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    body: str = Field(min_length=1, max_length=20_000)
    actor_kind: ActorKind
    status: Literal["open", "review", "resolved"]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    anchor_text: str | None = Field(default=None, max_length=4_000)

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comment body must not be blank")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("comment body must be UTF-8") from exc
        return value

    @field_validator("anchor_text")
    @classmethod
    def _anchor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


__all__ = ["ActorKind", "ArtifactComment", "ArtifactFolder", "ArtifactKind",
           "ArtifactRecord", "ArtifactVersion", "ArtifactWriteResult",
           "MAX_CONTENT_BYTES", "PublicationNotice", "validate_content",
           "validate_folder_name"]
