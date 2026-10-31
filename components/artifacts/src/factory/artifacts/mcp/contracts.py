"""Strict Artifacts MCP contracts."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..runtime.models import (
    ArtifactComment, ArtifactFolder, ArtifactRecord, ArtifactVersion,
    ArtifactWriteResult, validate_content,
)


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ArtifactRefInput(DTO):
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")


class ArtifactRevisionInput(ArtifactRefInput):
    expected_revision: int = Field(ge=1)


class SaveArtifactInput(DTO):
    name: str = Field(min_length=1, max_length=200)
    content: str
    description: str = Field(default="", max_length=2_000)
    kind: Literal["widget", "html", "markdown", "svg", "json", "text"] = "markdown"
    tags: list[str] = Field(default_factory=list, max_length=16)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128,
                                        pattern=r"^[A-Za-z0-9_.:-]+$")

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return validate_content(value)


class UpdateArtifactInput(ArtifactRevisionInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    description: str | None = Field(default=None, max_length=2_000)
    kind: Literal["widget", "html", "markdown", "svg", "json", "text"] | None = None
    tags: list[str] | None = Field(default=None, max_length=16)

    @field_validator("content")
    @classmethod
    def _content(cls, value: str | None) -> str | None:
        return validate_content(value) if value is not None else None

    @model_validator(mode="after")
    def _changed(self) -> "UpdateArtifactInput":
        if all(getattr(self, field) is None for field in
               ("name", "content", "description", "kind", "tags")):
            raise ValueError("artifact update requires a change")
        return self


class RevertArtifactInput(ArtifactRevisionInput):
    version: int = Field(ge=1)


class ListArtifactsInput(DTO):
    limit: int = Field(default=100, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=10_000)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["widget", "html", "markdown", "svg", "json", "text"] | None = None
    tag: str | None = Field(default=None, min_length=1, max_length=64)


class ArtifactOutput(DTO):
    artifact: ArtifactRecord


class ArtifactsOutput(DTO):
    artifacts: list[ArtifactRecord]


class ArtifactVersionsOutput(DTO):
    versions: list[ArtifactVersion]


class ArtifactWriteOutput(DTO):
    result: ArtifactWriteResult
    event_published: bool = False
    warning: str | None = None


class TombstoneOutput(DTO):
    slug: str
    tombstoned: bool
    event_published: bool = False
    warning: str | None = None


class EmptyInput(DTO):
    pass


class FolderCreateInput(DTO):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class FolderRevisionInput(DTO):
    folder_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    expected_revision: int = Field(ge=1)


class FolderRenameInput(FolderRevisionInput):
    name: str = Field(min_length=1, max_length=100)


class FolderMoveInput(FolderRevisionInput):
    parent_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class ArtifactMoveInput(ArtifactRevisionInput):
    folder_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class CommentBodyInput(ArtifactRefInput):
    body: str = Field(min_length=1, max_length=20_000)
    anchor_text: str | None = Field(default=None, min_length=1, max_length=4_000)

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("comment body must be UTF-8") from exc
        if not value.strip():
            raise ValueError("comment body must not be blank")
        return value


class CommentReplyInput(CommentBodyInput):
    parent_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class CommentRefInput(ArtifactRefInput):
    comment_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class CommentRevisionInput(CommentRefInput):
    expected_revision: int = Field(ge=1)


class FolderOutput(DTO):
    folder: "ArtifactFolder"


class FoldersOutput(DTO):
    folders: list["ArtifactFolder"]


class CommentOutput(DTO):
    comment: "ArtifactComment"
    event_published: bool = False
    warning: str | None = None


class CommentsOutput(DTO):
    comments: list["ArtifactComment"]


class ArtifactMoveOutput(DTO):
    artifact: ArtifactRecord
    event_published: bool = False
    warning: str | None = None


class DeleteOutput(DTO):
    id: str
    deleted: bool


__all__ = ["ArtifactMoveInput", "ArtifactMoveOutput", "ArtifactOutput",
           "ArtifactRefInput", "ArtifactRevisionInput", "ArtifactsOutput",
           "ArtifactVersionsOutput", "ArtifactWriteOutput", "CommentBodyInput",
           "CommentOutput", "CommentRefInput", "CommentReplyInput",
           "CommentRevisionInput", "CommentsOutput", "DeleteOutput", "DTO",
           "EmptyInput", "FolderCreateInput", "FolderMoveInput", "FolderOutput",
           "FolderRenameInput", "FolderRevisionInput", "FoldersOutput",
           "ListArtifactsInput", "RevertArtifactInput", "SaveArtifactInput",
           "TombstoneOutput", "UpdateArtifactInput"]
