"""Operational project command MCP tool."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import (
    ToolResult, get_run_id, op_kind, operational,
)
from factory.mcp_utils.registration import typed_tool

from .binding import project_binding
from .contracts import (
    CancelCommandInput, CancelCommandOutput, EditFileInput, FileWriteOutput,
    RunCommandInput, RunCommandOutput, WriteFileInput,
)


def register(mcp: Any, runtime: Any) -> None:
    @typed_tool(mcp)
    @operational(input_model=WriteFileInput, output_model=FileWriteOutput)
    @op_kind("write")
    async def devtools_write_file(
        path: str, content: str, envelope: dict | None = None,
    ) -> ToolResult[FileWriteOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(runtime.create_file, binding, path, content)
        return FileWriteOutput(result=result)

    @typed_tool(mcp)
    @operational(input_model=EditFileInput, output_model=FileWriteOutput)
    @op_kind("write")
    async def devtools_edit_file(
        path: str, content: str, base_sha256: str,
        envelope: dict | None = None,
    ) -> ToolResult[FileWriteOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(
            runtime.edit_file, binding, path, content, base_sha256,
        )
        return FileWriteOutput(result=result)

    @typed_tool(mcp)
    @operational(input_model=RunCommandInput, output_model=RunCommandOutput)
    @op_kind("shell")
    async def devtools_run_command(
        argv: list[str], cwd: str = ".", timeout_seconds: float = 60.0,
        output_limit: int = 65_536, envelope: dict | None = None,
    ) -> ToolResult[RunCommandOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(
            runtime.run_command, binding, argv, cwd,
            timeout_seconds=timeout_seconds, output_limit=output_limit,
            correlation_id=get_run_id(),
        )
        return RunCommandOutput(result=result)

    @typed_tool(mcp)
    @operational(input_model=CancelCommandInput, output_model=CancelCommandOutput)
    @op_kind("shell")
    async def devtools_cancel_command(
        run_id: str, envelope: dict | None = None,
    ) -> ToolResult[CancelCommandOutput]:
        binding = await project_binding(envelope)
        cancelled = runtime.cancel_command(binding, run_id)
        return CancelCommandOutput(run_id=run_id, cancelled=cancelled)


__all__ = ["register"]
