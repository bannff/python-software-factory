"""Generic callback failure and registration-level telemetry exclusion canaries."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registry import get_service, set_service
from factory.mcp_utils.runtime.native_v2_composer import (
    NativeMCPV2Composer, NativeToolRegistration,
)
from factory.mcp_utils.runtime.server_surface import (
    ServerCompositionPlan, ServerSurfaceIdentity,
)
from factory.mcp_utils.runtime.tool_result import ToolResult, ok


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    arguments: str
    envelope: dict[str, str] | None
    brick_name: str
    tool_name: str


class OutputDTO(BaseModel):
    received: bool


class FakeServer:
    def __init__(self, name: str, *, on_list_tools: Any, on_call_tool: Any) -> None:
        self.on_list_tools, self.on_call_tool = on_list_tools, on_call_tool


class Value:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mcp.server.Server", FakeServer)
    monkeypatch.setattr("mcp.types.Tool", Value)
    monkeypatch.setattr("mcp.types.ListToolsResult", Value)
    monkeypatch.setattr("mcp.types.TextContent", Value)
    monkeypatch.setattr("mcp.types.CallToolResult", Value)


def _plan() -> ServerCompositionPlan:
    identity = ServerSurfaceIdentity(
        entry_point="test", route_bindings=("/mcp",),
        transport_bindings=("in_process",), process_lifecycle_id="test",
        catalog_digest="catalog", scope_digest="scope",
        policy_digest="policy", closure_digest="closure",
    )
    return ServerCompositionPlan(identity, "flat", frozenset({"call_brick_tool"}))


def _server(handler: Any, **registration: Any) -> Any:
    item = NativeToolRegistration(
        "call_brick_tool", "", handler, **registration,
    )
    return NativeMCPV2Composer(_plan(), (item,)).compose()


@pytest.mark.asyncio
async def test_unknown_nonmapping_and_unexpected_faults_are_generic(monkeypatch) -> None:
    _patch(monkeypatch)

    @operational(input_model=InputDTO, output_model=OutputDTO)
    def explode(**_: Any) -> ToolResult[OutputDTO]:
        raise RuntimeError("secret-callback-canary")

    server = _server(explode)
    results = [
        await server.on_call_tool(None, SimpleNamespace(name="missing", arguments={})),
        await server.on_call_tool(None, SimpleNamespace(
            name="call_brick_tool", arguments=["not", "mapping"],
        )),
        await server.on_call_tool(None, SimpleNamespace(
            name="call_brick_tool", arguments={
                "arguments": "secret-callback-canary", "envelope": "secret",
                "brick_name": "demo", "tool_name": "demo_tool",
            },
        )),
    ]
    assert all(item.is_error for item in results)
    assert all(item.structured_content["error"] == "tool_execution_failed" for item in results)
    assert "secret-callback-canary" not in repr(results)


@pytest.mark.asyncio
async def test_registration_excludes_opaque_carriers_from_events_and_sink(monkeypatch) -> None:
    _patch(monkeypatch)
    events: list[dict[str, Any]] = []
    persisted: list[Any] = []
    received: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "factory.mcp_utils.runtime.native_v2_instrumentation.event_bus.publish",
        events.append,
    )
    previous = get_service("tool_invocation_sink")
    set_service("tool_invocation_sink", lambda *args, **kwargs: persisted.append((args, kwargs)))

    @operational(input_model=InputDTO, output_model=OutputDTO)
    def handler(**kwargs: Any) -> ToolResult[OutputDTO]:
        received.append(kwargs)
        return ok(OutputDTO(received=True))

    server = _server(
        handler, brick_name="mcp_server", source_name="call_brick_tool",
        telemetry_excluded_argument_fields=frozenset({"arguments"}),
        telemetry_excluded_envelope_fields=frozenset({"envelope"}),
    )
    canary = "serialized-payload-secret"
    try:
        result = await server.on_call_tool(None, SimpleNamespace(
            name="call_brick_tool", arguments={
                "arguments": canary, "envelope": canary,
                "brick_name": "demo", "tool_name": "demo_tool",
            },
        ))
    finally:
        set_service("tool_invocation_sink", previous)
    assert result.structured_content["ok"] is True
    assert received[0]["arguments"] == canary and received[0]["envelope"] == {}
    assert canary not in repr(events)
    assert canary not in repr(persisted)
    assert all(
        event.get("args_summary", {}).get("brick_name") == "demo"
        for event in events
    )
