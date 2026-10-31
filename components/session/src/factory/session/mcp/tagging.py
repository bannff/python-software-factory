"""Operational Session tag mutation MCP tool."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import SessionOutput, SetTagsInput
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SetTagsInput, output_model=SessionOutput)
    def session_set_tags(
        session_id: str, tags: tuple[str, ...], expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_tags(
            *identity(runtime, envelope), session_id, tags, expected_revision,
        )))


__all__ = ["register"]
