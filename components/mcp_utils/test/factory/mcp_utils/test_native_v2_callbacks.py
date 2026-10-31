"""Isolated public-MCP-v2 callback canaries; production still pins MCP v1."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.runtime.native_v2_capability_client import (
    NativeV2ScopedCapabilityClient,
)
from factory.mcp_utils.runtime.native_v2_composer import (
    NativeMCPV2Composer,
    NativeToolRegistration,
)
from factory.mcp_utils.runtime.scoped_capabilities import (
    CapabilityInvocation,
    CapabilityScope,
)
from factory.mcp_utils.runtime.server_surface import (
    ServerCompositionPlan,
    ServerSurfaceIdentity,
)
from factory.mcp_utils.runtime.tool_result import ToolResult, ok
from factory.mcp_utils.runtime.typed_boundary import apply_category


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int


class OutputDTO(BaseModel):
    value: int


class FakeServer:
    def __init__(self, name: str, *, on_list_tools: Any, on_call_tool: Any) -> None:
        self.name = name
        self.on_list_tools = on_list_tools
        self.on_call_tool = on_call_tool


class FakeClient:
    def __init__(self, server: FakeServer, **_: Any) -> None:
        self.server = server
        self.entered = False
        self.closed = False

    async def __aenter__(self) -> "FakeClient":
        self.entered = True
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.closed = True

    async def list_tools(self) -> Any:
        return await self.server.on_list_tools(None, None)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self.server.on_call_tool(None, SimpleNamespace(name=name, arguments=arguments))


class FakeTool:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class FakeListToolsResult:
    def __init__(self, *, tools: list[FakeTool]) -> None:
        self.tools = tools


class FakeTextContent:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class FakeCallToolResult:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def _plan() -> ServerCompositionPlan:
    identity = ServerSurfaceIdentity(
        entry_point="v2-canary", route_bindings=("/mcp",),
        transport_bindings=("in_process",), process_lifecycle_id="test",
        catalog_digest="catalog", scope_digest="scope", policy_digest="policy",
        closure_digest="closure",
    )
    return ServerCompositionPlan(identity, "flat", frozenset({"echo"}))


def _patch_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp
    import mcp.server
    import mcp.types

    monkeypatch.setattr(mcp.server, "Server", FakeServer)
    monkeypatch.setattr(mcp.types, "Tool", FakeTool)
    monkeypatch.setattr(mcp.types, "ListToolsResult", FakeListToolsResult)
    monkeypatch.setattr(mcp.types, "TextContent", FakeTextContent)
    monkeypatch.setattr(mcp.types, "CallToolResult", FakeCallToolResult)
    monkeypatch.setattr(mcp, "Client", FakeClient, raising=False)


@pytest.mark.asyncio
async def test_public_callbacks_preserve_flat_schema_and_tool_result_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_v2(monkeypatch)
    values: list[int] = []

    def echo(value: int) -> ToolResult[OutputDTO]:
        values.append(value)
        return ok(OutputDTO(value=value))

    handler = apply_category(echo, "deterministic", input_model=InputDTO, output_model=OutputDTO)
    server = NativeMCPV2Composer(_plan(), (NativeToolRegistration("echo", "Echo", handler),)).compose()
    listed = await server.on_list_tools(None, None)
    result = await server.on_call_tool(None, SimpleNamespace(name="echo", arguments={"value": 7}))

    assert listed.tools[0].input_schema == InputDTO.model_json_schema(mode="validation")
    assert values == [7]
    assert result.structured_content == {"schema_version": "v1", "ok": True, "data": {"value": 7}, "error": None, "idempotency_key": None}


@pytest.mark.asyncio
async def test_in_process_client_scopes_discovery_invocation_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_v2(monkeypatch)

    def echo(value: int) -> ToolResult[OutputDTO]:
        return ok(OutputDTO(value=value))

    handler = apply_category(echo, "deterministic", input_model=InputDTO, output_model=OutputDTO)
    server = NativeMCPV2Composer(_plan(), (NativeToolRegistration("echo", "Echo", handler),)).compose()
    client = NativeV2ScopedCapabilityClient(server, CapabilityScope.create("policy", {"echo"}))

    assert [item.name for item in await client.list_capabilities()] == ["echo"]
    result = await client.invoke(CapabilityInvocation("echo", {"value": 3}, "key"))
    assert result.structured_content is not None and result.structured_content["data"] == {"value": 3}
    await client.close()
    with pytest.raises(RuntimeError, match="closed"):
        await client.list_capabilities()
