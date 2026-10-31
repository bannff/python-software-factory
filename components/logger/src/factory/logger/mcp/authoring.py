"""Strict typed authoring MCP tools for the Logger brick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring, ok
from factory.mcp_utils.registration import typed_tool

from .contracts import ClearOutput, EmptyInput

if TYPE_CHECKING:
    from ..runtime.runtime import LoggerRuntime


_SAFE_FAILURE = "logger_operation_failed"


def register(mcp: Any, runtime: "LoggerRuntime") -> None:
    """Register authoring tools with strict flat ingress and typed egress."""

    @typed_tool(mcp, name="logger.clear")
    @authoring(input_model=EmptyInput, output_model=ClearOutput)
    def clear() -> ToolResult[ClearOutput]:
        """Clear log data without exposing the underlying filesystem path."""
        try:
            return ok(ClearOutput(status=runtime.clear()["status"]))
        except Exception:
            return ToolResult(ok=False, error=_SAFE_FAILURE)
