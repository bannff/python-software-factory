from __future__ import annotations

import httpx
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from factory.mcp_utils.interface import (
    CapabilityAccessError, CapabilityDescriptor, CapabilityInvocation,
    CapabilityResult, CapabilityScope, ScopedWorkloadProxy,
    build_workload_proxy_app, build_workload_proxy_server,
)

_SCHEMA = {
    "type": "object", "properties": {"entity_id": {"type": "string"}},
    "required": ["entity_id"], "additionalProperties": False,
}


class Upstream:
    def __init__(self, scope):
        self.scope, self.closed, self.calls = scope, False, []

    async def list_capabilities(self):
        return (CapabilityDescriptor("graph_get_entity", "Get entity", _SCHEMA),)

    async def invoke(self, request):
        self.calls.append(request)
        return CapabilityResult(
            content=({"type": "text", "text": "ok"},),
            structured_content={"ok": True, "entity_id": request.arguments["entity_id"]},
        )

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_proxy_exact_scope_rotation_and_close() -> None:
    scope = CapabilityScope.create("workload:launch", ["graph_get_entity"])
    first, second = Upstream(scope), Upstream(scope)
    proxy = ScopedWorkloadProxy(first, scope)
    with pytest.raises(CapabilityAccessError):
        await proxy.invoke(CapabilityInvocation("memory_store", {}, "k"))
    await proxy.rotate(second)
    assert first.closed
    await proxy.close()
    assert second.closed
    with pytest.raises(CapabilityAccessError):
        await proxy.list_capabilities()


@pytest.mark.asyncio
async def test_proxy_is_real_mcp_v2_with_exact_schema_and_invocation() -> None:
    scope = CapabilityScope.create("workload:launch", ["graph_get_entity"])
    upstream = Upstream(scope)
    async with Client(build_workload_proxy_server(
        ScopedWorkloadProxy(upstream, scope))) as client:
        listed = await client.list_tools()
        result = await client.call_tool("graph_get_entity", {"entity_id": "e-1"})
        denied = await client.call_tool("memory_store", {})
    assert [(tool.name, tool.input_schema) for tool in listed.tools] == [
        ("graph_get_entity", _SCHEMA)]
    assert result.structured_content == {"ok": True, "entity_id": "e-1"}
    assert denied.is_error is True
    assert upstream.calls[0].name == "graph_get_entity"
    assert upstream.calls[0].arguments == {"entity_id": "e-1"}
    assert upstream.calls[0].idempotency_key.startswith("workload-proxy:")


@pytest.mark.asyncio
async def test_proxy_streamable_http_is_bearer_free_mcp() -> None:
    scope = CapabilityScope.create("workload:launch", ["graph_get_entity"])
    upstream = Upstream(scope)
    app = build_workload_proxy_app(ScopedWorkloadProxy(upstream, scope))
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=transport, base_url="http://localhost:8000",
    ) as http_client:
        connection = streamable_http_client(
            "http://localhost:8000/mcp", http_client=http_client)
        async with Client(connection) as client:
            listed = await client.list_tools()
            result = await client.call_tool(
                "graph_get_entity", {"entity_id": "e-2"})
    assert [tool.name for tool in listed.tools] == ["graph_get_entity"]
    assert result.structured_content["entity_id"] == "e-2"
    assert "authorization" not in repr(upstream.calls).lower()


@pytest.mark.asyncio
async def test_close_waits_for_inflight_and_denies_post_close_admission() -> None:
    import asyncio
    scope = CapabilityScope.create("workload:launch", ["graph_get_entity"])
    upstream = Upstream(scope)
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked(request):
        entered.set()
        await release.wait()
        return CapabilityResult(content=(), structured_content={"ok": True})

    upstream.invoke = blocked
    proxy = ScopedWorkloadProxy(upstream, scope)
    call = asyncio.create_task(proxy.invoke(CapabilityInvocation(
        "graph_get_entity", {"entity_id": "e"}, "key")))
    await entered.wait()
    closing = asyncio.create_task(proxy.close())
    await asyncio.sleep(0)
    assert not closing.done() and not upstream.closed
    release.set()
    await call
    await closing
    assert upstream.closed
    with pytest.raises(CapabilityAccessError):
        await proxy.invoke(CapabilityInvocation(
            "graph_get_entity", {"entity_id": "late"}, "late"))


@pytest.mark.asyncio
async def test_rotate_serializes_with_inflight_list() -> None:
    import asyncio
    scope = CapabilityScope.create("workload:launch", ["graph_get_entity"])
    first, second = Upstream(scope), Upstream(scope)
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_list():
        entered.set()
        await release.wait()
        return (CapabilityDescriptor("graph_get_entity", "Get", _SCHEMA),)

    first.list_capabilities = blocked_list
    proxy = ScopedWorkloadProxy(first, scope)
    listing = asyncio.create_task(proxy.list_capabilities())
    await entered.wait()
    rotating = asyncio.create_task(proxy.rotate(second))
    await asyncio.sleep(0)
    assert not rotating.done() and not first.closed
    release.set()
    await listing
    await rotating
    assert first.closed and not second.closed
