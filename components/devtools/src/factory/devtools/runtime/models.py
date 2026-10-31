"""Strict records for project-scoped developer operations."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProjectBinding(StrictModel):
    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    root: str = Field(min_length=1, max_length=4096)


class FileRead(StrictModel):
    path: str
    content: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_bytes: int = Field(ge=0)
    truncated: bool = False


class DirectoryEntry(StrictModel):
    path: str
    kind: str
    size: int | None = Field(default=None, ge=0)


class FileWrite(StrictModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    total_bytes: int = Field(ge=0)
    created: bool


class DirectoryListing(StrictModel):
    path: str
    entries: tuple[DirectoryEntry, ...]
    truncated: bool = False


class CommandResult(StrictModel):
    run_id: str = Field(pattern=r"^cmd_[0-9a-f]{32}$")
    argv: tuple[str, ...]
    cwd: str
    stdout: str = Field(max_length=131_072)
    stderr: str = Field(max_length=131_072)
    exit_code: int
    duration_ms: int = Field(ge=0)
    timed_out: bool
    cancelled: bool
    truncated: bool
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GitResult(StrictModel):
    operation: str
    output: str = Field(max_length=131_072)
    paths: tuple[str, ...] = ()
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    branch: str | None = None
    truncated: bool = False


class SearchMatch(StrictModel):
    path: str
    line: int | None = Field(default=None, ge=1)
    text: str = Field(max_length=4096)


class SearchResult(StrictModel):
    matches: tuple[SearchMatch, ...]
    truncated: bool
    files_scanned: int = Field(ge=0)


class RelativePath(StrictModel):
    path: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def _relative(self) -> "RelativePath":
        import pathlib
        value = pathlib.PurePath(self.path)
        if value.is_absolute() or any(part in {"", ".", ".."} for part in value.parts):
            raise ValueError("path must be project-relative without traversal")
        if "\x00" in self.path or any(ord(char) < 32 for char in self.path):
            raise ValueError("path contains control characters")
        return self


__all__ = ["CommandResult", "DirectoryEntry", "DirectoryListing", "FileRead", "FileWrite",
           "GitResult", "ProjectBinding", "RelativePath", "SearchMatch", "SearchResult"]
