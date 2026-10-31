"""Typed extended operational MCP tools for the sandbox brick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from factory.mcp_utils.interface import fail, ok, op_kind, operational
from factory.mcp_utils.runtime.tool_result import ToolResult

from .conversions import to_runtime_service_mocks
from typing import Literal

from .extended_models import (
    SandboxChangedFile, SandboxCommandRequest, SandboxCommandResult, SandboxDiffRequest,
    SandboxDiffResult, SandboxFileTransferRequest, SandboxFileTransferResult,
    SandboxServiceMocksRequest, SandboxServiceMocksResult, SandboxWorkspaceResult,
    SandboxWriteFileRequest, SandboxWriteFileResult,
)
from .nested_models import SandboxServiceMockConfig
from .models import SandboxEnvironmentRequest

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime


def _transfer_result(
    raw: dict[str, Any], env_id: str, local_path: str, remote_path: str,
) -> ToolResult[SandboxFileTransferResult]:
    if not raw.get("success", False):
        return fail(str(raw.get("error", "sandbox file transfer failed")))
    return ok(SandboxFileTransferResult(
        env_id=env_id,
        local_path=raw.get("local_path", local_path),
        remote_path=raw.get("remote_path", remote_path),
        size_bytes=raw.get("size_bytes"),
    ))


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register typed stateful sandbox operations."""

    @mcp.tool(
        name="sandbox.execute",
        telemetry_excluded_argument_fields=("command",),
    )
    @operational(input_model=SandboxCommandRequest, output_model=SandboxCommandResult)
    @op_kind("shell")
    async def execute(
        env_id: str = Field(min_length=1, max_length=256),
        command: str = Field(min_length=1, max_length=10_000),
        timeout_seconds: int = Field(default=300, ge=1, le=3600),
    ) -> ToolResult[SandboxCommandResult]:
        """Execute a command; nonzero exits are data, not transport failures."""
        return ok(SandboxCommandResult.model_validate(
            (await runtime.execute(env_id, command, timeout_seconds)).model_dump(),
        ))

    @mcp.tool(name="sandbox.upload_file")
    @operational(
        input_model=SandboxFileTransferRequest,
        output_model=SandboxFileTransferResult,
    )
    @op_kind("write")
    async def upload_file(
        env_id: str = Field(min_length=1, max_length=256),
        local_path: str = Field(min_length=1, max_length=4096),
        remote_path: str = Field(min_length=1, max_length=4096),
    ) -> ToolResult[SandboxFileTransferResult]:
        """Upload a file to a sandbox environment."""
        return _transfer_result(
            await runtime.upload_file(env_id, local_path, remote_path),
            env_id, local_path, remote_path,
        )

    @mcp.tool(name="sandbox.download_file")
    @operational(
        input_model=SandboxFileTransferRequest,
        output_model=SandboxFileTransferResult,
    )
    @op_kind("write")
    async def download_file(
        env_id: str = Field(min_length=1, max_length=256),
        remote_path: str = Field(min_length=1, max_length=4096),
        local_path: str = Field(min_length=1, max_length=4096),
    ) -> ToolResult[SandboxFileTransferResult]:
        """Download a file to the caller-visible local destination."""
        return _transfer_result(
            await runtime.download_file(env_id, remote_path, local_path),
            env_id, local_path, remote_path,
        )

    @mcp.tool(name="sandbox.write_file")
    @operational(input_model=SandboxWriteFileRequest, output_model=SandboxWriteFileResult)
    @op_kind("write")
    async def write_file(
        env_id: str = Field(min_length=1, max_length=256),
        remote_path: str = Field(min_length=1, max_length=4096),
        content: str = Field(default="", max_length=5_000_000),
        encoding: Literal["utf8", "base64"] = "utf8",
    ) -> ToolResult[SandboxWriteFileResult]:
        """Write inline content to a file inside the sandbox (no host staging)."""
        raw = await runtime.write_file(env_id, remote_path, content, encoding)
        if not raw.get("success", False):
            return fail(str(raw.get("error", "sandbox write_file failed")))
        return ok(SandboxWriteFileResult(
            env_id=env_id, remote_path=raw.get("remote_path", remote_path),
            bytes_written=int(raw.get("bytes_written", 0)),
        ))

    @mcp.tool(name="sandbox.diff")
    @operational(input_model=SandboxDiffRequest, output_model=SandboxDiffResult)
    async def diff(
        env_id: str = Field(min_length=1, max_length=256),
        path: str = Field(default=".", min_length=1, max_length=4096),
    ) -> ToolResult[SandboxDiffResult]:
        """Report changed files under a path via git; empty when not a repo."""
        raw = await runtime.diff(env_id, path)
        return ok(SandboxDiffResult(
            env_id=env_id,
            path=raw.get("path", path),
            is_git_repo=bool(raw.get("is_git_repo", False)),
            files=[SandboxChangedFile(**f) for f in raw.get("files", [])],
            stat=raw.get("stat", ""),
        ))

    @mcp.tool(name="sandbox.apply_service_mocks")
    @operational(
        input_model=SandboxServiceMocksRequest,
        output_model=SandboxServiceMocksResult,
    )
    @op_kind("write")
    async def apply_service_mocks(
        env_id: str = Field(min_length=1, max_length=256),
        config: SandboxServiceMockConfig = Field(...),
    ) -> ToolResult[SandboxServiceMocksResult]:
        """Apply a validated service-mock configuration."""
        raw = await runtime.apply_service_mocks(
            env_id, to_runtime_service_mocks(SandboxServiceMockConfig.model_validate(config)),
        )
        if raw.get("error"):
            return fail(str(raw["error"]))
        return ok(SandboxServiceMocksResult(
            env_id=raw.get("env_id", env_id),
            mocks_applied=raw.get("mocks_applied", []),
        ))

    @mcp.tool(name="sandbox.workspace_dir")
    @operational(
        input_model=SandboxEnvironmentRequest,
        output_model=SandboxWorkspaceResult,
    )
    @op_kind("write")
    def get_workspace_dir(
        env_id: str = Field(min_length=1, max_length=256),
    ) -> ToolResult[SandboxWorkspaceResult]:
        """Get or create a safe per-environment artifact staging directory."""
        return ok(SandboxWorkspaceResult(
            env_id=env_id, workspace_dir=str(runtime.workspace_dir(env_id)),
        ))
