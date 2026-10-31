"""Tests for the unified Starlette app (create_app).

Verifies that MCP, REST, SSE, and AG-UI routes are all mounted
correctly on a single process with no double-prefix bugs.
"""
from __future__ import annotations

from pathlib import Path
import os

import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create the real local-auth unified app."""
    values = {
        "MCP_LOCAL_AUTH": "true",
        "MCP_LOCAL_AUTH_TOKEN": "unified-local-token-1234",
        "MCP_AUTH_AUDIENCE": "companion-x",
        "AUTH_CONFIG_DIR": "projects/companion_x/config/auth",
        "MCP_PERMISSIONS_CONFIG_DIR": "config/mcp_permissions",
        "TELEMETRY_REQUIRED": "0",
        "MCP_SERVER_NAME": "unified-auth-test",
    }
    previous = {key: os.environ.get(key) for key in values}
    from factory.mcp_utils.interface import get_service, set_service
    previous_controller = get_service("mcp_access_controller")
    previous_verifier = get_service("mcp_token_verifier")
    os.environ.update(values)
    import factory.mcp_server.core as core
    core._server = core._aggregator = None
    app = core.create_app()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        set_service("mcp_access_controller", previous_controller)
        set_service("mcp_token_verifier", previous_verifier)
        core._server = core._aggregator = None
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class TestUnifiedApp:
    """Verify the unified server mounts all transports correctly."""

    def test_imports_workspace_source(self):
        """The unified app tests must run against workspace source, not site-packages."""
        import factory.mcp_server.core as core

        resolved = Path(core.__file__).resolve().as_posix()
        assert "/bases/mcp_server/src/" in resolved

    def test_health_endpoint(self, client):
        """GET /api/health returns 200 with gateway info."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway"] == "unified"
        assert data["status"] == "healthy"

    def test_no_tool_invocation_routes_remain(self, client):
        """bd:python-factory-736 — the REST bridge's tool-invocation routes
        (``/api/tools``, ``/api/tools/{name}``) are retired. Real MCP
        ``tools/call`` against ``/mcp`` is the only tool-invocation
        transport now. Guards against the shim quietly coming back."""
        paths = {getattr(route, "path", None) for route in client.app.routes}
        assert "/api/tools" not in paths
        assert not any(
            p and p.startswith("/api/tools/") for p in paths if p is not None
        )

    def test_mcp_endpoint_requires_bearer(self, client):
        """The real unified /mcp mount rejects anonymous requests."""
        resp = client.post("/mcp", json={})
        assert resp.status_code == 401
        assert "Bearer" in resp.headers["www-authenticate"]

    def test_mcp_not_double_prefixed(self, client):
        """POST /mcp/mcp should 404 (proves no double-prefix bug)."""
        resp = client.post("/mcp/mcp", json={})
        assert resp.status_code == 404

    def test_ag_ui_endpoint(self, client):
        """POST /ag-ui/run should be handled (not 404)."""
        resp = client.post("/ag-ui/run", json={"messages": []})
        assert resp.status_code != 404

    def test_sse_endpoint(self, client):
        """SSE tool-stream route is registered and CORS preflight responds."""
        route = next(
            route for route in client.app.routes
            if getattr(route, "path", None) == "/api/events/tools" and "GET" in route.methods
        )
        assert route is not None

        resp = client.options("/api/events/tools", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "GET" in resp.headers.get("access-control-allow-methods", "")

    def test_mcp_cors_preflight(self, client):
        """Allowlisted browser origin can preflight /mcp (bd:python-factory-iqm3h).

        The dashboard (:3000) reaches /mcp cross-origin.
        Before app-wide CORSMiddleware, the mounted FastMCP app answered the
        OPTIONS preflight with 405 and no ACAO, so the browser blocked the MCP
        handshake and tool discovery never populated.
        """
        resp = client.options("/mcp/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "POST" in resp.headers.get("access-control-allow-methods", "")

    def test_cors_exposes_mcp_session_header(self, client):
        """Browser clients must be able to READ mcp-session-id off responses."""
        resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "mcp-session-id" in resp.headers.get(
            "access-control-expose-headers", "").lower()
