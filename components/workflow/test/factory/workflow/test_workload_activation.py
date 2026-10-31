from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from factory.auth.interface import WorkloadGrant
from factory.mcp_utils.interface import (
    CapabilityDescriptor, CapabilityResult, CapabilityScope,
    ScopedWorkloadProxy, build_workload_proxy_app,
)
from factory.workflow.runtime.adapters.uds_proxy_host import UvicornUDSProxyHost
from factory.workflow.runtime.adapters.workload_proxy import WorkloadProxyActivator
from factory.workflow.runtime.workload_lifecycle import WorkloadLaunchManifest


class Upstream:
    def __init__(self, scope):
        self.scope, self.closed = scope, False

    async def list_capabilities(self):
        return ()

    async def invoke(self, _request):
        raise AssertionError("not invoked")

    async def close(self):
        self.closed = True


class Host:
    def __init__(self):
        self.app, self.unmounted = None, []

    async def mount(self, app, *, launch_id):
        self.app = app
        return f"unix:///tmp/{launch_id}.sock"

    async def unmount(self, endpoint):
        self.unmounted.append(endpoint)


def _manifest():
    grant = WorkloadGrant.create(
        launch_id="launch", generation=1, tenant_id="tenant",
        audience="companion-x", allowed_tools=["graph_get_entity"])
    return WorkloadLaunchManifest(
        "run", "attempt", 0, grant.manifest_digest, grant, "tenant")


@pytest.mark.asyncio
async def test_activator_builds_exact_scope_and_returns_only_endpoint() -> None:
    captured = {}

    async def upstream_factory(token: str, scope: CapabilityScope):
        captured.update(token=token, scope=scope)
        captured["upstream"] = Upstream(scope)
        return captured["upstream"]

    host = Host()
    activator = WorkloadProxyActivator(upstream_factory, host)
    endpoint = await activator.activate(_manifest(), "secret-canary-token")
    assert endpoint == "unix:///tmp/launch.sock"
    assert captured["scope"].tool_names == frozenset({"graph_get_entity"})
    assert "secret-canary-token" not in endpoint + repr(host.app)
    await activator.deactivate(endpoint)
    assert host.unmounted == [endpoint]
    assert captured["upstream"].closed


@pytest.mark.asyncio
async def test_uvicorn_uds_host_secures_socket_and_cleans_up(tmp_path: Path) -> None:
    import tempfile
    del tmp_path
    root = Path(tempfile.mkdtemp(prefix="pf-uds-", dir="/tmp"))
    async def health(_request):
        return PlainTextResponse("ok")

    host = UvicornUDSProxyHost(root)
    endpoint = await host.mount(
        Starlette(routes=[Route("/health", health)]), launch_id="launch")
    socket_path = Path(endpoint.removeprefix("unix://"))
    assert socket_path.is_socket()
    assert os.stat(root).st_mode & 0o777 == 0o700
    assert os.stat(socket_path).st_mode & 0o777 == 0o600
    transport = httpx.AsyncHTTPTransport(uds=str(socket_path))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost") as client:
        assert (await client.get("/health")).text == "ok"
    await host.unmount(endpoint)
    assert not socket_path.exists()
    root.rmdir()


def test_workflow_factory_resolves_caller_bound_invoker_without_domain_branching() -> None:
    from factory.mcp_utils.interface import get_service, set_service
    from factory.workflow.runtime.workload_factory import create_workload_lifecycle
    calls = []

    def invoker_factory(caller):
        calls.append(caller)
        return lambda *_args, **_kwargs: None

    async def upstream_factory(_token, scope):
        return Upstream(scope)

    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", invoker_factory)
    try:
        coordinator = create_workload_lifecycle(
            upstream_factory=upstream_factory, proxy_host=Host())
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert calls == ["workflow"]
    assert coordinator._activator.__class__.__name__ == "WorkloadProxyActivator"


@pytest.mark.asyncio
async def test_real_mcp_proxy_round_trip_over_restrictive_uds() -> None:
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    import tempfile

    scope = CapabilityScope.create("workload:launch", ["graph_get_entity"])

    class MCPUpstream(Upstream):
        async def list_capabilities(self):
            return (CapabilityDescriptor(
                "graph_get_entity", "Get entity",
                {"type": "object", "properties": {}, "additionalProperties": False},
            ),)

        async def invoke(self, _request):
            return CapabilityResult(
                content=(), structured_content={"ok": True, "id": "entity"})

    root = Path(tempfile.mkdtemp(prefix="pf-mcp-uds-", dir="/tmp"))
    host = UvicornUDSProxyHost(root)
    app = build_workload_proxy_app(
        ScopedWorkloadProxy(MCPUpstream(scope), scope))
    endpoint = await host.mount(app, launch_id="launch")
    socket_path = endpoint.removeprefix("unix://")
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost:80",
            headers={"Host": "localhost:80"},
        ) as http_client:
            async with Client(streamable_http_client(
                "http://localhost:80/mcp", http_client=http_client,
            )) as client:
                listed = await client.list_tools()
                allowed = await client.call_tool("graph_get_entity", {})
                denied = await client.call_tool("memory_store", {})
        assert [tool.name for tool in listed.tools] == ["graph_get_entity"]
        assert allowed.structured_content == {"ok": True, "id": "entity"}
        assert denied.is_error
    finally:
        await host.unmount(endpoint)
        root.rmdir()


def test_authenticated_upstream_requires_https_or_explicit_local_loopback(
    monkeypatch,
) -> None:
    from factory.workflow.runtime.adapters.authenticated_upstream import (
        AuthenticatedHTTPUpstreamFactory,
    )

    for url in ("http://example.test/mcp", "ftp://example.test/mcp",
                "https://user:secret@example.test/mcp"):
        with pytest.raises(ValueError, match="HTTPS"):
            AuthenticatedHTTPUpstreamFactory(url)
    assert AuthenticatedHTTPUpstreamFactory("https://example.test/mcp")
    monkeypatch.setenv("MCP_LOCAL_AUTH", "true")
    assert AuthenticatedHTTPUpstreamFactory("http://127.0.0.1:8000/mcp")
