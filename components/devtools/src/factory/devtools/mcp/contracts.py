"""Strict Devtools MCP contracts."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.models import (
    CommandResult, DirectoryListing, FileRead, FileWrite, GitResult, SearchResult,
)


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EnvelopeInput(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    thread_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    workflow_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    timestamp: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class RunCommandInput(DTO):
    argv: list[str] = Field(min_length=1, max_length=64)
    cwd: str = Field(default=".", min_length=1, max_length=2048)
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=120.0)
    output_limit: int = Field(default=65_536, ge=1024, le=131_072)
    envelope: EnvelopeInput | None = None



class CancelCommandInput(DTO):
    run_id: str = Field(pattern=r"^cmd_[0-9a-f]{32}$")
    envelope: EnvelopeInput | None = None


class CancelCommandOutput(DTO):
    run_id: str
    cancelled: bool

class RunCommandOutput(DTO):
    result: CommandResult


class GitStatusInput(DTO):
    envelope: EnvelopeInput | None = None


class GitPathsInput(DTO):
    paths: list[str] = Field(min_length=1, max_length=64)
    envelope: EnvelopeInput | None = None


class GitDiffInput(GitPathsInput):
    staged: bool = False


class GitLogInput(DTO):
    paths: list[str] = Field(default_factory=list, max_length=64)
    limit: int = Field(default=20, ge=1, le=100)
    envelope: EnvelopeInput | None = None


class GitCommitInput(DTO):
    message: str = Field(min_length=1, max_length=1000)
    skip_hooks: bool = False
    envelope: EnvelopeInput | None = None


class GitPushInput(DTO):
    remote: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    branch: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    set_upstream: bool = False
    envelope: EnvelopeInput | None = None


class GitOutput(DTO):
    result: GitResult




class ReadFileInput(DTO):
    path: str = Field(min_length=1, max_length=2048)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=2000, ge=1, le=10_000)
    envelope: EnvelopeInput | None = None


class ListDirInput(DTO):
    path: str = Field(default=".", min_length=1, max_length=2048)
    limit: int = Field(default=500, ge=1, le=2000)
    envelope: EnvelopeInput | None = None


class SearchInput(DTO):
    query: str = Field(min_length=1, max_length=512)
    path: str = Field(default=".", min_length=1, max_length=2048)
    glob: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=100, ge=1, le=500)
    envelope: EnvelopeInput | None = None


class WriteFileInput(DTO):
    path: str = Field(min_length=1, max_length=2048)
    content: str = Field(max_length=1_048_576)
    envelope: EnvelopeInput | None = None


class EditFileInput(WriteFileInput):
    base_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FileReadOutput(DTO):
    result: FileRead


class DirectoryOutput(DTO):
    result: DirectoryListing


class SearchOutput(DTO):
    result: SearchResult


class AllowedProjectRootsOutput(DTO):
    roots: list[str]


class FileWriteOutput(DTO):
    result: FileWrite


__all__ = [
    "CancelCommandInput", "CancelCommandOutput", "AllowedProjectRootsOutput",
    "DirectoryOutput", "EditFileInput", "FileReadOutput", "FileWriteOutput",
    "GitCommitInput", "GitDiffInput", "GitLogInput", "GitOutput",
    "GitPathsInput", "GitPushInput", "GitStatusInput", "ListDirInput",
    "ReadFileInput", "RunCommandInput", "RunCommandOutput", "SearchInput",
    "SearchOutput", "WriteFileInput",
]
