"""Real native-v2 integration for progressive global and flat Agent scope."""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import (
    CapabilityInvocation, ToolResult, ok, operational, service_only,
)
from factory.mcp_utils.runtime.scoped_capability_client import CapabilityAccessError
from factory.mcp_utils.runtime.tool_catalog import CatalogTool, ToolCatalog


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str


def _catalog() -> ToolCatalog:
    catalog = ToolCatalog("demo")

    @catalog.tool(name="echo")
    @operational(input_model=_Input, output_model=_Output)
    def echo(value: str) -> ToolResult[_Output]:
        return ok(_Output(value=value))

    @catalog.tool(name="internal")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_Input, output_model=_Output)
    def internal(value: str) -> ToolResult[_Output]:
        return ok(_Output(value=value))

    catalog.add_tool(CatalogTool("untyped", "", lambda: {}))
    return catalog


@pytest.mark.asyncio
async def test_agent_scope_uses_separate_flat_server_without_mutating_progressive(monkeypatch) -> None:
    from mcp import Client
    from factory.agent.runtime.adapters import _scoped_client
    from factory.mcp_server import core
    from factory.mcp_server.runtime.aggregator import MCPAggregator
    from factory.mcp_server.runtime.native_meta import META_TOOL_NAMES
    from factory.mcp_server.runtime.native_v2_bootstrap import build_configured_native_server

    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = _catalog()
    progressive, _ = build_configured_native_server(
        aggregator, server_name="global-progressive", discovery_mode="progressive",
    )
    monkeypatch.setattr(core, "_aggregator", aggregator)
    monkeypatch.setattr(core, "_server", progressive)

    async with Client(progressive) as client:
        global_names = {tool.name for tool in (await client.list_tools()).tools}
    assert global_names == set(META_TOOL_NAMES)

    scoped = _scoped_client()
    try:
        assert [item.name for item in await scoped.list_capabilities()] == ["demo_echo"]
        result = await scoped.invoke(CapabilityInvocation(
            "demo_echo", {"value": "admitted"}, "invoke-1",
        ))
        assert result.is_error is False
        assert result.structured_content["data"] == {"value": "admitted"}
        for denied in ("demo_internal", "demo_untyped", "outside_scope"):
            with pytest.raises(CapabilityAccessError, match="outside scope"):
                await scoped.invoke(CapabilityInvocation(denied, {}, "denied"))
    finally:
        await scoped.close()

    assert core.get_server() is progressive
    async with Client(progressive) as client:
        names_after = {tool.name for tool in (await client.list_tools()).tools}
    assert names_after == set(META_TOOL_NAMES)


@pytest.mark.asyncio
async def test_real_in_process_agent_spawn_subagent_uses_trusted_scope(monkeypatch) -> None:
    from types import SimpleNamespace
    from mcp import Client
    from factory.agent.mcp.spawn_tools import register
    from factory.agent.runtime.runtime_contracts import RuntimeResult
    from factory.agent.runtime.spawn import SpawnCoordinator
    from factory.mcp_server.runtime.aggregator import MCPAggregator
    from factory.mcp_server.runtime.scoped_surface import create_exact_flat_surface
    from factory.mcp_utils.interface import (
        bind_capability_scope, reset_capability_scope,
    )

    catalog = ToolCatalog("agent")
    registry = SimpleNamespace(get=lambda agent_id: SimpleNamespace(id=agent_id))
    register(catalog, SimpleNamespace(agent_registry=registry))
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["agent"])
    aggregator._lazy._cache["agent"] = catalog
    server, scope = create_exact_flat_surface(
        aggregator, {"agent_spawn_subagent"},
    )

    class Agents:
        capability_scope_digest = scope.digest

        async def invoke(self, request):
            return RuntimeResult(request.invocation_id, "spawned", "completed")

    class Graph:
        async def close(self):
            return None

    monkeypatch.setattr(
        SpawnCoordinator, "_pair", lambda self, parent: (Agents(), Graph()),
    )
    token = bind_capability_scope(scope)
    try:
        async with Client(server) as client:
            result = await client.call_tool(
                "agent_spawn_subagent", {"agent_id": "writer", "task": "draft"},
            )
    finally:
        reset_capability_scope(token)
    assert result.is_error is False
    assert result.structured_content["data"]["output"] == "spawned"


@pytest.mark.asyncio
async def test_native_scope_projects_canonical_correlation_into_strict_envelope() -> None:
    from typing import Any
    from factory.mcp_server.runtime.aggregator import MCPAggregator
    from factory.mcp_server.runtime.scoped_surface import create_exact_flat_surface
    from factory.mcp_utils.interface import NativeV2ScopedCapabilityClient

    class Envelope(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        tenant_id: str | None = None
        principal_id: str | None = None
        session_id: str | None = None
        correlation_id: str | None = None
        agent_id: str | None = None
        attributes: dict[str, Any] = {}

    class Input(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        value: str
        envelope: Envelope | None = None

    catalog = ToolCatalog("strict-envelope")
    seen = []

    @catalog.tool(name="echo")
    @operational(input_model=Input, output_model=_Output)
    def echo(value: str, envelope: dict | None = None) -> ToolResult[_Output]:
        seen.append(envelope)
        return ok(_Output(value=value))

    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = catalog
    server, scope = create_exact_flat_surface(aggregator, {"demo_echo"})
    client = NativeV2ScopedCapabilityClient(server, scope)
    try:
        assert [item.name for item in await client.list_capabilities()] == ["demo_echo"]
        result = await client.invoke(CapabilityInvocation(
            "demo_echo", {"value": "ok"}, "key",
            correlation={
                "tenant_id": "tenant", "principal_id": "owner",
                "session_id": "thread", "correlation_id": "run",
                "agent_id": "developer", "untrusted_extra": "drop",
            },
        ))
    finally:
        await client.close()
    assert result.is_error is False
    assert seen == [{
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "thread", "correlation_id": "run",
        "agent_id": "developer", "attributes": {},
    }]
