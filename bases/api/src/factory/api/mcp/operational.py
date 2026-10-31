"""Operational MCP tools for API base."""

from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, ok, operational

from ..core import AdapterType
from ..runtime.runtime import APIRuntime
from .contracts.models import (
    AddRouteInput,
    AddRouteOutput,
    RemoveRouteInput,
    RemoveRouteOutput,
    SwitchAdapterInput,
    SwitchAdapterOutput,
)


def register(mcp: Any, get_runtime: Callable[[], APIRuntime]) -> None:
    """Register operational tools with the MCP server."""

    @mcp.tool(name="api.add_route")
    @operational(input_model=AddRouteInput, output_model=AddRouteOutput)
    def add_route(
        path: str, method: str = "GET", handler_name: str = "noop",
        tags: list[str] | None = None,
    ) -> ToolResult[AddRouteOutput]:
        """Register a new route on the API."""
        def _placeholder(**kwargs: Any) -> dict[str, Any]:
            return {"handler": handler_name, "args": kwargs}

        get_runtime().add_route(path, method.upper(), _placeholder, tags or [])
        return ok(AddRouteOutput(
            registered=True, path=path, method=method.upper(), handler=handler_name,
        ))

    @mcp.tool(name="api.remove_route")
    @operational(input_model=RemoveRouteInput, output_model=RemoveRouteOutput)
    def remove_route(path: str, method: str = "GET") -> ToolResult[RemoveRouteOutput]:
        """Remove a route from the API."""
        runtime = get_runtime()
        adapter = runtime.get_adapter()
        if hasattr(adapter, "remove_route"):
            adapter.remove_route(path, method.upper())
            return ok(RemoveRouteOutput(removed=True, path=path, method=method.upper()))
        return ok(RemoveRouteOutput(
            removed=False, path=path, method=method.upper(),
            reason="Adapter does not support route removal",
            routes_count=len(runtime.list_routes()),
        ))

    @mcp.tool(name="api.switch_adapter")
    @operational(input_model=SwitchAdapterInput, output_model=SwitchAdapterOutput)
    def switch_adapter(adapter_type: str) -> ToolResult[SwitchAdapterOutput]:
        """Switch the API adapter (rest or graphql)."""
        available = APIRuntime.available_backends()
        if adapter_type not in available:
            return ok(SwitchAdapterOutput(
                switched=False, requested=adapter_type,
                error=f"Unknown adapter: {adapter_type}", available=available,
            ))
        runtime = get_runtime()
        runtime._adapter_type = AdapterType(adapter_type)
        runtime._adapter = None
        return ok(SwitchAdapterOutput(switched=True, adapter=adapter_type))
