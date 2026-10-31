from __future__ import annotations

import asyncio
import httpx
from pydantic import BaseModel, ConfigDict
import yaml

from factory.auth.access import RuntimeCredentialVerifier
from factory.auth.interface import (
    LocalOpaqueWorkloadCredentialProvider, Runtime, WorkloadGrant,
)
from factory.auth.server import create_tool_catalog
from factory.mcp_server.runtime.access_control import GatewayAccessController, SDKTokenVerifier
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_server.runtime.native_v2_bootstrap import build_configured_native_server
from factory.mcp_server.runtime.native_v2_http import build_streamable_http_app
from factory.mcp_server.runtime.workload_grant_policy import GatewayWorkloadGrantPolicy
from factory.mcp_utils.interface import (
    ToolResult, authoring, deterministic, get_service, ok, operational, set_service,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


class Empty(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Output(BaseModel):
    value: str


class AllowDecisionPoint:
    def decide(self, **_kwargs):
        return {"decision": "allow", "reason": "test-policy", "policy_id": "test"}


def _setup(tmp_path, effects):
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump({
        "service_name": "test", "backend": "memory"}))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = Runtime(
        tmp_path, workload_credentials=LocalOpaqueWorkloadCredentialProvider(),
    )
    auth, demo = create_tool_catalog(runtime), ToolCatalog("demo")

    def add(name, decorator):
        @demo.tool(name=name)
        @decorator(input_model=Empty, output_model=Output)
        def tool() -> ToolResult[Output]:
            effects.append(name)
            return ok(Output(value=name))

    add("demo.leaf", operational)
    add("demo.other", deterministic)
    add("demo.authoring.change", authoring)
    add("get_capabilities", deterministic)
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["auth", "demo"])
    aggregator._lazy._cache.update({"auth": auth, "demo": demo})
    controller = GatewayAccessController(AllowDecisionPoint())
    server, _ = build_configured_native_server(
        aggregator, server_name="workload-http-test", discovery_mode="flat",
        access_controller=controller,
    )
    return aggregator, runtime, server


def _issue(aggregator, grant):
    binding = {"workflow_run_id": "run", "attempt_id": "attempt",
               "revision": 0, "manifest_digest": grant.manifest_digest}
    result = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
        {"brick_name": "auth", "tool_name": "auth.issue_workload_credential"},
        arguments={**binding, "grant": grant.model_dump(mode="json")},
        idempotency_key="issue", envelope={"run_id": "run", "tenant_id": "tenant"},
        attempt=binding,
    )
    private = result["result"]["structured_content"]["data"]["credential"]
    return private["access_token"], private["credential"]["credential_id"], binding


def test_real_http_workload_scope_and_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    effects = []
    aggregator, runtime, server = _setup(tmp_path, effects)
    previous = get_service("workload_grant_policy")
    set_service("workload_grant_policy", GatewayWorkloadGrantPolicy(aggregator))
    grant = WorkloadGrant.create(
        launch_id="launch", generation=1, tenant_id="tenant",
        audience="companion-x", allowed_tools=["demo_leaf"])
    token, credential_id, binding = _issue(aggregator, grant)
    try:
        from mcp.client.streamable_http import streamable_http_client
        from mcp import Client
        from mcp.server.auth.settings import AuthSettings
        app = build_streamable_http_app(
            server, path="/mcp",
            auth=AuthSettings(
                issuer_url="http://test", resource_server_url="http://test/mcp"),
            token_verifier=SDKTokenVerifier(
                RuntimeCredentialVerifier(runtime), "companion-x"), host="test",
        )

        async def exercise():
            transport = httpx.ASGITransport(app=app)
            async with app.router.lifespan_context(app), httpx.AsyncClient(
                transport=transport, base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                async with Client(streamable_http_client(
                    "http://test/mcp", http_client=client)) as mcp:
                    listed = await mcp.list_tools()
                    allowed = await mcp.call_tool("demo_leaf", {})
                    denied = [await mcp.call_tool(name, {}) for name in (
                        "demo_other", "demo_authoring_change",
                        "demo_get_capabilities", "auth_auth_verify_access_token",
                    )]
                revoke = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
                    {"brick_name": "auth", "tool_name": "auth.revoke_workload_credential"},
                    arguments={**binding, "credential_id": credential_id},
                    idempotency_key=f"revoke:{credential_id}",
                    envelope={"run_id": "run", "tenant_id": "tenant"},
                    attempt=binding,
                )
                initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2025-11-25",
                              "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}}}
                after = await client.post("/mcp", json=initialize)
            return listed, allowed, denied, revoke, after

        listed, allowed, denied, revoke, after = asyncio.run(exercise())
        assert [item.name for item in listed.tools] == ["demo_leaf"]
        assert allowed.structured_content["data"]["value"] == "demo.leaf"
        assert all(item.is_error for item in denied)
        assert effects == ["demo.leaf"]
        assert revoke["result"]["structured_content"]["data"]["revoked"]
        assert after.status_code == 401
        assert token not in repr(denied) + after.text
    finally:
        set_service("workload_grant_policy", previous)
