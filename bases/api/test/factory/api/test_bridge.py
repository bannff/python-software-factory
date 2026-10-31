"""Tests for the native MCP-v2 API bridge and its REST projection.

The generic ``/api/tools/{tool_name}`` endpoint delegates naming and aliases to
the aggregator's canonical resolver; health and persona routes remain dedicated
reads. In-process helpers are retained for AG-UI and view actions.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest


def _make_mock_aggregator(tool_names=None, health=None, caps=None, invoke_results=None):
    agg = MagicMock()
    agg.get_all_tool_names.return_value = tool_names or []
    agg.get_aggregated_health.return_value = health or {"status": "healthy"}
    agg.get_aggregated_capabilities.return_value = caps or {}
    if invoke_results:
        agg.invoke_tool.side_effect = lambda name, **kw: invoke_results.get(name)
    return agg


def _patch_aggregator(agg):
    return patch("factory.api.runtime.bridge._get_aggregator", return_value=agg)


class TestToolMap:
    def test_extracts_tools_from_mcp(self):
        from factory.api.runtime.bridge import _get_tools
        mock_tool_map = {"kb_search": MagicMock(), "health_check": MagicMock()}
        with patch("factory.api.runtime.bridge.get_tool_map", return_value=mock_tool_map), \
             patch("factory.api.runtime.bridge._get_mcp_server", return_value=MagicMock()):
            result = _get_tools()
        assert "kb_search" in result
        assert len(result) == 2

    def test_empty_when_no_tools(self):
        from factory.api.runtime.bridge import _get_tools
        with patch("factory.api.runtime.bridge.get_tool_map", return_value={}), \
             patch("factory.api.runtime.bridge._get_mcp_server", return_value=MagicMock()):
            assert _get_tools() == {}


class TestCallTool:
    """``_call_tool`` is a library fn — ``ag_ui_routes.py`` calls it directly."""

    @pytest.mark.asyncio
    async def test_calls_tool_via_aggregator(self):
        from factory.api.runtime.bridge import _call_tool
        agg = _make_mock_aggregator()
        agg.invoke_tool.return_value = {"echoed": True}
        with _patch_aggregator(agg):
            result = await _call_tool("echo", {"msg": "hi"})
        assert result == {"echoed": True}
        agg.invoke_tool.assert_called_once_with("echo", msg="hi")

    @pytest.mark.asyncio
    async def test_returns_none_when_aggregator_unavailable(self):
        from factory.api.runtime.bridge import _call_tool
        with _patch_aggregator(None):
            assert await _call_tool("nonexistent", {}) is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invoke_exception(self):
        from factory.api.runtime.bridge import _call_tool
        agg = _make_mock_aggregator()
        agg.invoke_tool.side_effect = RuntimeError("boom")
        with _patch_aggregator(agg):
            assert await _call_tool("bad_tool", {}) is None

    @pytest.mark.asyncio
    async def test_awaits_coroutine_result(self):
        from factory.api.runtime.bridge import _call_tool
        async def async_result():
            return {"async": True}
        agg = _make_mock_aggregator()
        agg.invoke_tool.return_value = async_result()
        with _patch_aggregator(agg):
            assert await _call_tool("async_tool", {}) == {"async": True}


class TestExtractEnvelopeForAGUI:
    """AG-UI accepts only complete principals from Auth's real typed result."""

    @pytest.mark.asyncio
    async def test_verified_bearer_token_yields_a_principal_envelope(self):
        from factory.api.runtime.bridge import _extract_envelope
        agg = _make_mock_aggregator(
            invoke_results={"auth_verify_access_token": {
                "ok": True, "data": {"ok": True, "principal": {
                    "subject": "user-1", "tenant_id": "tenant-1",
                }},
            }},
        )
        request = MagicMock()
        request.headers = {"authorization": "Bearer token-123"}
        with _patch_aggregator(agg):
            envelope = await _extract_envelope(request)
        assert envelope == {"principal_id": "user-1", "tenant_id": "tenant-1"}

    @pytest.mark.asyncio
    async def test_missing_bearer_header_yields_no_envelope(self):
        from factory.api.runtime.bridge import _extract_envelope
        request = MagicMock()
        request.headers = {}
        assert await _extract_envelope(request) is None

    @pytest.mark.asyncio
    async def test_rejected_token_yields_no_envelope(self):
        from factory.api.runtime.bridge import _extract_envelope
        agg = _make_mock_aggregator(
            invoke_results={"auth_verify_access_token": {
                "ok": True, "data": {"ok": False, "principal": {
                    "subject": "attacker", "tenant_id": "tenant-1",
                }},
            }},
        )
        request = MagicMock()
        request.headers = {"authorization": "Bearer bad-token"}
        with _patch_aggregator(agg):
            assert await _extract_envelope(request) is None


class TestBridgeRoutes:
    """Generic tool projection plus dedicated health and persona reads."""

    def _make_aggregator(self):
        return _make_mock_aggregator(
            tool_names=["kb_search", "health_check", "get_capabilities"],
            health={"status": "healthy"},
            caps={"registered_bricks": 2, "total_tools": 5},
            invoke_results={
                "agent_get_agent_registry": [],
            },
        )

    def _make_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from factory.api.runtime.bridge import register_bridge_routes

        app = FastAPI()
        register_bridge_routes(app)
        return TestClient(app)

    def test_list_personas_delegates_to_get_agent_registry(self):
        """bd:d4roe.3 — GET /api/personas is a thin read passthrough to
        the agent brick's ``agent_get_agent_registry`` MCP tool (verdict
        ``a19ef414`` Q3). It owns no persona data of its own."""
        personas = [
            {"id": "companion-x-default", "name": "Companion X",
             "description": "default", "model": "claude"},
            {"id": "grape-grower", "name": "Grape Grower",
             "description": "wine", "model": "claude"},
        ]
        agg = _make_mock_aggregator(
            tool_names=["agent_get_agent_registry"],
            invoke_results={"agent_get_agent_registry": personas},
        )
        with _patch_aggregator(agg):
            client = self._make_client()
            resp = client.get("/api/personas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert data["personas"] == personas
        agg.invoke_tool.assert_called_once_with("agent_get_agent_registry")

    def test_list_personas_empty_when_tool_returns_non_list(self):
        """Defensive: a None / non-list result yields an empty list, not
        a 500 — keeps the FE palette resilient."""
        agg = _make_mock_aggregator(
            tool_names=["agent_get_agent_registry"],
            invoke_results={"agent_get_agent_registry": None},
        )
        with _patch_aggregator(agg):
            client = self._make_client()
            resp = client.get("/api/personas")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"personas": [], "count": 0}

    def test_health_endpoint(self):
        agg = self._make_aggregator()
        with _patch_aggregator(agg), \
             patch("factory.api.runtime.views.ensure_views_registered"):
            client = self._make_client()
            resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway"] == "http"
        assert data["status"] == "healthy"
        import os
        assert data["process_id"] == os.getpid()
        assert "launch_id" in data
        assert data["total_tools"] == 3
        assert data["mcp_health"] == {"status": "healthy"}
        assert data["capabilities"]["registered_bricks"] == 2

    def test_health_fallback_without_aggregator(self):
        mock_tool_map = {
            "health_check": MagicMock(return_value={"status": "ok"}),
            "get_capabilities": MagicMock(return_value={"bricks": 1}),
        }
        with _patch_aggregator(None), \
             patch("factory.api.runtime.bridge.get_tool_map", return_value=mock_tool_map), \
             patch("factory.api.runtime.bridge._get_mcp_server", return_value=MagicMock()):
            client = self._make_client()
            resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tools"] == 2
        assert data["mcp_health"] == {"status": "ok"}
