"""Deterministic git read MCP tools."""
from __future__ import annotations

import asyncio
from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, op_kind
from factory.mcp_utils.registration import typed_tool

from .binding import project_binding
from .contracts import (
    AllowedProjectRootsOutput, DirectoryOutput, FileReadOutput, GitDiffInput,
    GitLogInput, GitOutput, GitStatusInput, ListDirInput, ReadFileInput,
    SearchInput, SearchOutput,
)


def register(mcp: Any, runtime: Any) -> None:
    @typed_tool(mcp)
    @deterministic(output_model=AllowedProjectRootsOutput)
    @op_kind("read")
    def devtools_list_allowed_project_roots() -> ToolResult[AllowedProjectRootsOutput]:
        from factory.devtools.interface import list_allowed_project_roots
        return AllowedProjectRootsOutput(roots=list_allowed_project_roots())

    @typed_tool(mcp)
    @deterministic(input_model=ReadFileInput, output_model=FileReadOutput)
    @op_kind("read")
    async def devtools_read_file(
        path: str, offset: int = 0, limit: int = 2000,
        envelope: dict | None = None,
    ) -> ToolResult[FileReadOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(runtime.read_file, binding, path, offset, limit)
        return FileReadOutput(result=result)

    @typed_tool(mcp)
    @deterministic(input_model=ListDirInput, output_model=DirectoryOutput)
    @op_kind("read")
    async def devtools_list_dir(
        path: str = ".", limit: int = 500,
        envelope: dict | None = None,
    ) -> ToolResult[DirectoryOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(runtime.list_dir, binding, path, limit)
        return DirectoryOutput(result=result)

    @typed_tool(mcp)
    @deterministic(input_model=SearchInput, output_model=SearchOutput)
    @op_kind("read")
    async def devtools_search(
        query: str, path: str = ".", glob: str | None = None,
        limit: int = 100, envelope: dict | None = None,
    ) -> ToolResult[SearchOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(
            runtime.search, binding, query, path, glob, limit,
        )
        return SearchOutput(result=result)

    @typed_tool(mcp)
    @deterministic(input_model=GitStatusInput, output_model=GitOutput)
    @op_kind("read")
    async def devtools_git_status(
        envelope: dict | None = None,
    ) -> ToolResult[GitOutput]:
        binding = await project_binding(envelope)
        return GitOutput(result=await asyncio.to_thread(runtime.git_status, binding))

    @typed_tool(mcp)
    @deterministic(input_model=GitDiffInput, output_model=GitOutput)
    @op_kind("read")
    async def devtools_git_diff(
        paths: list[str], staged: bool = False,
        envelope: dict | None = None,
    ) -> ToolResult[GitOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(runtime.git_diff, binding, paths, staged=staged)
        return GitOutput(result=result)

    @typed_tool(mcp)
    @deterministic(input_model=GitLogInput, output_model=GitOutput)
    @op_kind("read")
    async def devtools_git_log(
        paths: list[str] | None = None, limit: int = 20,
        envelope: dict | None = None,
    ) -> ToolResult[GitOutput]:
        binding = await project_binding(envelope)
        result = await asyncio.to_thread(runtime.git_log, binding, paths, limit=limit)
        return GitOutput(result=result)


__all__ = ["register"]
