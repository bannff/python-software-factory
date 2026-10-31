"""Public MCP 2.1.1 transport canaries for strict category-decorated tools.

Run this module in the isolated MCP v2 environment.  It proves that the
public HTTP and stdio clients preserve flat strict ingress and never execute a
handler when a string is supplied for its integer field.
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.runtime.native_v2_composer import (
    NativeMCPV2Composer,
    NativeToolRegistration,
)
from factory.mcp_utils.runtime.server_surface import (
    ServerCompositionPlan,
    ServerSurfaceIdentity,
)
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

pytestmark = pytest.mark.skipif(
    importlib.metadata.version("mcp") != "2.1.1",
    reason="requires the isolated mcp==2.1.1 transport environment",
)


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int


class OutputDTO(BaseModel):
    value: int
    invocation: int


def _server(calls: list[int]) -> Any:
    @deterministic(input_model=InputDTO, output_model=OutputDTO)
    def echo(value: int) -> ToolResult[OutputDTO]:
        calls.append(value)
        return ok(OutputDTO(value=value, invocation=len(calls)))

    identity = ServerSurfaceIdentity(
        entry_point="native-v2-transport-canary",
        route_bindings=("/mcp",),
        transport_bindings=("http", "stdio"),
        process_lifecycle_id="test",
        catalog_digest="catalog",
        scope_digest="scope",
        policy_digest="policy",
        closure_digest="closure",
    )
    plan = ServerCompositionPlan(identity, "flat", frozenset({"echo"}))
    return NativeMCPV2Composer(plan, (NativeToolRegistration("echo", "Echo", echo),)).compose()


async def _assert_contract(session: Any, calls: list[int]) -> None:
    await session.initialize()
    assert [tool.name for tool in (await session.list_tools()).tools] == ["echo"]
    success = await session.call_tool("echo", {"value": 7})
    assert success.is_error is False
    assert success.structured_content == {
        "schema_version": "v1", "ok": True,
        "data": {"value": 7, "invocation": 1},
        "error": None, "idempotency_key": None,
    }
    invalid = await session.call_tool("echo", {"value": "7"})
    assert invalid.is_error is True
    after_invalid = await session.call_tool("echo", {"value": 8})
    assert after_invalid.structured_content["data"] == {"value": 8, "invocation": 2}
    if calls:
        assert calls == [7, 8]


@pytest.mark.asyncio
async def test_http_client_rejects_string_for_strict_integer_without_execution() -> None:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    calls: list[int] = []
    manager = StreamableHTTPSessionManager(_server(calls), stateless=True)
    transport = httpx.ASGITransport(app=manager.handle_request)
    async with manager.run(), httpx.AsyncClient(transport=transport, base_url="http://canary") as client:
        async with streamable_http_client("http://canary/mcp", http_client=client) as streams:
            async with ClientSession(*streams) as session:
                await _assert_contract(session, calls)


@pytest.mark.asyncio
async def test_stdio_client_rejects_string_for_strict_integer_without_execution() -> None:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--stdio"],
    )
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await _assert_contract(session, [])


async def _serve_stdio() -> None:
    from mcp.server.stdio import stdio_server

    server = _server([])
    async with stdio_server() as streams:
        await server.run(*streams, server.create_initialization_options())


if __name__ == "__main__":
    if sys.argv[1:] != ["--stdio"]:
        raise SystemExit("expected --stdio")
    asyncio.run(_serve_stdio())
