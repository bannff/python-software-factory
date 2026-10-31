"""Typed operational MCP tools for the Worker base."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts.operational import (
    ExecuteToolInput,
    ExecuteToolOutput,
    ListMcpToolsOutput,
    SendTaskInput,
    SendTaskOutput,
)
from .contracts.base import EmptyInput, JsonArray, JsonObject
from .projections import safe_json

if TYPE_CHECKING:
    from ..runtime.runtime import WorkerRuntime


def register(mcp: Any, get_runtime: Callable[[], "WorkerRuntime"]) -> None:
    """Register stateful Worker operations with strict DTOs."""

    @typed_tool(mcp, name="worker.send_task")
    @operational(input_model=SendTaskInput, output_model=SendTaskOutput)
    def send_task(
        name: str,
        args: JsonArray | None = None,
        kwargs: JsonObject | None = None,
    ) -> ToolResult[SendTaskOutput]:
        """Dispatch a task while preserving positional and keyword arguments."""
        try:
            result = get_runtime().send_task(name, tuple(args or []), kwargs)
            return {
                "dispatched": True,
                "task": name,
                "result": safe_json(result),
                "error": None,
            }
        except Exception:
            return {
                "dispatched": False,
                "task": name,
                "result": None,
                "error": "worker_dispatch_failed",
            }

    @typed_tool(mcp, name="worker.execute_tool")
    @operational(input_model=ExecuteToolInput, output_model=ExecuteToolOutput)
    def execute_tool(
        tool_name: str,
        arguments: JsonObject | None = None,
    ) -> ToolResult[ExecuteToolOutput]:
        """Execute an allowlisted MCP tool through the public bridge seam."""
        from ..runtime.bridge import execute_mcp_tool

        try:
            raw = execute_mcp_tool(tool_name, arguments)
        except Exception:
            raw = {"tool": tool_name, "error": "bridge_invocation_failed"}
        if not isinstance(raw, dict):
            raw = {"tool": tool_name, "error": "bridge_result_unavailable"}
        available = raw.get("available", [])
        return {
            "tool": tool_name,
            "result": safe_json(raw.get("result")),
            "error": raw.get("error") if isinstance(raw.get("error"), str) else None,
            "available": [item for item in available if isinstance(item, str)]
            if isinstance(available, list) else [],
        }

    @typed_tool(mcp, name="worker.list_mcp_tools")
    @operational(input_model=EmptyInput, output_model=ListMcpToolsOutput)
    def list_mcp_tools() -> ToolResult[ListMcpToolsOutput]:
        """List only MCP tools permitted by the Worker bridge policy."""
        from ..runtime.bridge import list_mcp_tools as _list

        try:
            raw = _list()
        except Exception:
            raw = {"tools": [], "count": 0, "error": "bridge_unavailable"}
        if not isinstance(raw, dict):
            raw = {"tools": [], "count": 0, "error": "bridge_result_unavailable"}
        tools = raw.get("tools", [])
        projected = [item for item in tools if isinstance(item, str)] if isinstance(tools, list) else []
        return {
            "tools": projected,
            "count": len(projected),
            "error": raw.get("error") if isinstance(raw.get("error"), str) else None,
        }


__all__ = ["register"]
