"""Operator-gated git authoring MCP tools."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from factory.mcp_utils.interface import ToolResult, authoring, fail, op_kind
from factory.mcp_utils.registration import typed_tool

from .binding import project_binding
from .contracts import (
    GitCommitInput, GitOutput, GitPathsInput, GitPushInput,
)


def authoring_enabled() -> bool:
    return os.getenv("DEVTOOLS_ENABLE_AUTHORING_TOOLS", "").lower() in {
        "1", "true", "yes",
    }


def register(mcp: Any, runtime: Any) -> None:
    @typed_tool(mcp)
    @authoring(input_model=GitPathsInput, output_model=GitOutput)
    @op_kind("authoring")
    async def devtools_git_stage(
        paths: list[str], envelope: dict | None = None,
    ) -> ToolResult[GitOutput]:
        if not authoring_enabled():
            return fail("authoring_disabled")
        binding = await project_binding(envelope)
        return GitOutput(result=await asyncio.to_thread(runtime.git_stage, binding, paths))

    @typed_tool(mcp)
    @authoring(input_model=GitCommitInput, output_model=GitOutput)
    @op_kind("authoring")
    async def devtools_git_commit(
        message: str, skip_hooks: bool = False,
        envelope: dict | None = None,
    ) -> ToolResult[GitOutput]:
        if not authoring_enabled():
            return fail("authoring_disabled")
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(
            runtime.git_commit, binding, message, skip_hooks=skip_hooks,
        )
        return GitOutput(result=result)

    @typed_tool(mcp)
    @authoring(input_model=GitPushInput, output_model=GitOutput)
    @op_kind("authoring")
    async def devtools_git_push(
        remote: str, branch: str, set_upstream: bool = False,
        envelope: dict | None = None,
    ) -> ToolResult[GitOutput]:
        if not authoring_enabled():
            return fail("authoring_disabled")
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(
            runtime.git_push, binding, remote, branch,
            set_upstream=set_upstream,
        )
        return GitOutput(result=result)


__all__ = ["authoring_enabled", "register"]
