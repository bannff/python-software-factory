from __future__ import annotations

import asyncio

import httpx
from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.native_v2_http import build_streamable_http_app
from factory.mcp_utils.interface import (
    NativeMCPV2Composer, NativeToolRegistration, ServerCompositionPlan,
    ServerSurfaceIdentity, ToolResult, ok, operational,
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Output(BaseModel):
    healthy: bool


class Verifier:
    async def verify_token(self, token: str):
        if token != "valid-local-token-1234":
            return None
        from mcp.server.auth.provider import AccessToken
        return AccessToken(
            token=token, client_id="client", scopes=[], subject="operator",
            claims={"tenant_id": "local", "roles": ["operator"]},
        )


def _server():
    @operational(input_model=Input, output_model=Output)
    def health() -> ToolResult[Output]:
        return ok(Output(healthy=True))

    identity = ServerSurfaceIdentity(
        entry_point="test", route_bindings=("/mcp",), transport_bindings=("http",),
        process_lifecycle_id="test", catalog_digest="a", scope_digest="b",
        policy_digest="c", closure_digest="d",
    )
    plan = ServerCompositionPlan(identity, "flat", frozenset({"demo_health"}))
    return NativeMCPV2Composer(
        plan, (NativeToolRegistration("demo_health", "", health),),
    ).compose()


def test_actual_mcp_requires_and_verifies_bearer_token() -> None:
    from mcp.server.auth.settings import AuthSettings

    app = build_streamable_http_app(
        _server(), path="/mcp", token_verifier=Verifier(),
        auth=AuthSettings(
            issuer_url="http://127.0.0.1:8000",
            resource_server_url="http://127.0.0.1:8000/mcp",
        ), host="test",
    )
    initialize = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }

    async def probe():
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                missing = await client.post("/mcp", json=initialize)
                invalid = await client.post(
                    "/mcp", json=initialize, headers={"Authorization": "Bearer bad"},
                )
                valid = await client.post(
                    "/mcp", json=initialize,
                    headers={"Authorization": "Bearer valid-local-token-1234"},
                )
        return missing, invalid, valid

    missing, invalid, valid = asyncio.run(probe())
    assert missing.status_code == invalid.status_code == 401
    assert "Bearer" in missing.headers["www-authenticate"]
    assert valid.status_code == 200
    assert "valid-local-token" not in valid.text


def test_api_composition_root_mount_requires_bearer(monkeypatch) -> None:
    values = {
        "MCP_LOCAL_AUTH": "true",
        "MCP_LOCAL_AUTH_TOKEN": "api-local-token-123456",
        "MCP_AUTH_AUDIENCE": "companion-x",
        "AUTH_CONFIG_DIR": "projects/companion_x/config/auth",
        "MCP_PERMISSIONS_CONFIG_DIR": "config/mcp_permissions",
        "MCP_SERVER_NAME": "api-auth-test",
        "TELEMETRY_REQUIRED": "0",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    import factory.mcp_server.core as core
    import factory.api.runtime.bridge as bridge
    from factory.mcp_utils.interface import get_service, set_service
    previous_controller = get_service("mcp_access_controller")
    previous_verifier = get_service("mcp_token_verifier")
    core._server = core._aggregator = None
    bridge._aggregator_server = bridge._aggregator = None
    from factory.api.main import create_app
    from starlette.testclient import TestClient

    initialize = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    try:
        with TestClient(
            create_app(), base_url="http://127.0.0.1:8000",
        ) as client:
            missing = client.post("/mcp/", json=initialize)
            valid = client.post(
                "/mcp/", json=initialize,
                headers={"Authorization": "Bearer api-local-token-123456"},
            )
    finally:
        set_service("mcp_access_controller", previous_controller)
        set_service("mcp_token_verifier", previous_verifier)
        core._server = core._aggregator = None
        bridge._aggregator_server = bridge._aggregator = None
    assert missing.status_code == 401
    assert "Bearer" in missing.headers["www-authenticate"]
    assert valid.status_code == 200
