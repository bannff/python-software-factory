"""Pydantic v2 MCP boundary models for extended sandbox operations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel
from .nested_models import SandboxEnvironmentInfo, SandboxServiceMockConfig


class SandboxCommandRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    command: str = Field(min_length=1, max_length=10_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class SandboxCommandResult(StrictModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class SandboxFileTransferRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    local_path: str = Field(min_length=1, max_length=4096)
    remote_path: str = Field(min_length=1, max_length=4096)


class SandboxFileTransferResult(StrictModel):
    success: Literal[True] = True
    env_id: str
    local_path: str
    remote_path: str
    size_bytes: int | None = Field(default=None, ge=0)


class SandboxEnvironmentListResult(StrictModel):
    environments: list[SandboxEnvironmentInfo] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class SandboxServiceMocksRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    config: SandboxServiceMockConfig


class SandboxServiceMocksResult(StrictModel):
    env_id: str
    mocks_applied: list[str] = Field(default_factory=list)


class SandboxReconResource(StrictModel):
    type: str | None = None
    name: str | None = None


class SandboxCfnRequest(StrictModel):
    resources: list[SandboxReconResource]
    description: str = Field(default="Auto-generated from discovered resources", min_length=1)


class SandboxSkippedReconResource(StrictModel):
    index: int = Field(ge=0)
    reason: Literal["missing_type", "missing_name", "unsupported_type"]


class SandboxCfnResult(StrictModel):
    template: dict[str, Any]
    generated_count: int = Field(ge=0)
    skipped: list[SandboxSkippedReconResource] = Field(default_factory=list)


class SandboxWorkspaceResult(StrictModel):
    env_id: str
    workspace_dir: str


class SandboxWriteFileRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    remote_path: str = Field(min_length=1, max_length=4096)
    content: str = Field(default="", max_length=5_000_000)
    encoding: Literal["utf8", "base64"] = "utf8"


class SandboxWriteFileResult(StrictModel):
    success: Literal[True] = True
    env_id: str
    remote_path: str
    bytes_written: int = Field(ge=0)


class SandboxDiffRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    path: str = Field(default=".", min_length=1, max_length=4096)


class SandboxChangedFile(StrictModel):
    status: str = Field(min_length=1, max_length=8)
    path: str = Field(min_length=1, max_length=4096)


class SandboxDiffResult(StrictModel):
    env_id: str
    path: str
    is_git_repo: bool
    files: list[SandboxChangedFile] = Field(default_factory=list)
    stat: str = ""


__all__ = [
    "SandboxCfnRequest", "SandboxCfnResult", "SandboxChangedFile",
    "SandboxCommandRequest", "SandboxCommandResult", "SandboxDiffRequest",
    "SandboxDiffResult", "SandboxEnvironmentListResult", "SandboxFileTransferRequest",
    "SandboxFileTransferResult", "SandboxReconResource",
    "SandboxServiceMocksRequest", "SandboxServiceMocksResult",
    "SandboxSkippedReconResource", "SandboxWorkspaceResult",
    "SandboxWriteFileRequest", "SandboxWriteFileResult",
]
