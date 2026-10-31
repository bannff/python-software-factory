"""Gateway callback composition canary for the public MCP-v2 activation seam."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from factory.mcp_server import interface as mcp_iface
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_utils.runtime.server_surface import (
    ServerCompositionPlan,
    ServerSurfaceIdentity,
)


class _Server:
    def __init__(self, name: str, *, on_list_tools: Any, on_call_tool: Any) -> None:
        self.name = name
        self.on_list_tools = on_list_tools
        self.on_call_tool = on_call_tool


class _Tool:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _ListToolsResult:
    def __init__(self, *, tools: list[_Tool]) -> None:
        self.tools = tools


class _TextContent:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _CallToolResult:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def _patch_v2(monkeypatch: Any) -> None:
    import mcp.server
    import mcp.types

    monkeypatch.setattr(mcp.server, "Server", _Server)
    monkeypatch.setattr(mcp.types, "Tool", _Tool)
    monkeypatch.setattr(mcp.types, "ListToolsResult", _ListToolsResult)
    monkeypatch.setattr(mcp.types, "TextContent", _TextContent)
    monkeypatch.setattr(mcp.types, "CallToolResult", _CallToolResult)


def _plan() -> ServerCompositionPlan:
    identity = ServerSurfaceIdentity(
        entry_point="factory.mcp_server:main",
        route_bindings=("/mcp",),
        transport_bindings=("in_process",),
        process_lifecycle_id="native-v2-gateway-canary",
        catalog_digest="catalog",
        scope_digest="scope",
        policy_digest="policy",
        closure_digest="closure",
    )
    return ServerCompositionPlan(identity, "flat", frozenset({"echo"}))


async def test_gateway_composes_selected_handler_through_native_callbacks(
    monkeypatch: Any,
) -> None:
    _patch_v2(monkeypatch)
    calls: list[int] = []

    def echo(value: int) -> Any:
        calls.append(value)
        from factory.mcp_utils.runtime.tool_result import ok
        return ok({"value": value})

    registration = SimpleNamespace(
        name="echo",
        description="Echo",
        handler=echo,
        input_schema=lambda: {"type": "object"},
    )
    monkeypatch.setattr(
        "factory.mcp_server.runtime.native_v2_view.resolve_selected_tools",
        lambda *_args, **_kwargs: (SimpleNamespace(native_registration=lambda: registration),),
    )
    monkeypatch.setattr(mcp_iface, "get_server", lambda: object())
    monkeypatch.setattr(mcp_iface, "get_aggregator", lambda: MCPAggregator(SimpleNamespace()))

    server = mcp_iface.get_native_v2_view(_plan(), {"echo"})
    listed = await server.on_list_tools(None, None)
    result = await server.on_call_tool(None, SimpleNamespace(name="echo", arguments={"value": 7}))

    assert [tool.name for tool in listed.tools] == ["echo"]
    assert calls == [7]
    assert result.structured_content["data"] == {"value": 7}
