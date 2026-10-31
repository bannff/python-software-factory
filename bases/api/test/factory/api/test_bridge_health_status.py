"""#68: /api/health top-level status must come from the brick aggregate."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_bridge import _make_mock_aggregator, _patch_aggregator


def test_health_top_level_status_reflects_degraded_bricks():
    """A brick that failed to register must not read healthy.

    gateway_health used to return a literal status:"healthy" while the real
    aggregate lived in mcp_health (#68) — a brick with zero tools still
    looked green to every operator surface.
    """
    agg = _make_mock_aggregator(
        tool_names=["kb_search", "health_check", "get_capabilities"],
        health={
            "status": "degraded", "healthy_bricks": 1, "total_bricks": 2,
            "bricks": {
                "demo": {"healthy": True, "error": None},
                "broken": {"healthy": False, "error": "boom"},
            },
        },
        caps={"registered_bricks": 2, "total_tools": 5},
    )
    from factory.api.runtime.bridge import register_bridge_routes
    app = FastAPI()
    register_bridge_routes(app)
    with _patch_aggregator(agg), \
         patch("factory.api.runtime.views.ensure_views_registered"):
        resp = TestClient(app).get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["mcp_health"]["healthy_bricks"] == 1
    assert data["mcp_health"]["total_bricks"] == 2


def test_health_unexpected_aggregate_status_fails_closed():
    """#68 fail-closed: an aggregate whose status is missing/unexpected is
    NOT proof of health — the top-level field must read degraded, never
    silently fall back to the old literal healthy."""
    agg = _make_mock_aggregator(
        tool_names=["kb_search", "health_check", "get_capabilities"],
        health={"healthy_bricks": 2, "total_bricks": 2,
                "bricks": {"a": {"healthy": True, "error": None},
                           "b": {"healthy": True, "error": None}}},
        caps={"registered_bricks": 2, "total_tools": 5},
    )
    from factory.api.runtime.bridge import register_bridge_routes
    app = FastAPI()
    register_bridge_routes(app)
    with _patch_aggregator(agg), \
         patch("factory.api.runtime.views.ensure_views_registered"):
        resp = TestClient(app).get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"


def test_health_fallback_mirrors_flat_map_status():
    """Flat-tool-map fallback: trust the map's own status, never assert."""
    mock_tool_map = {
        "health_check": MagicMock(return_value={"status": "degraded"}),
        "get_capabilities": MagicMock(return_value={"bricks": 1}),
    }
    from factory.api.runtime.bridge import register_bridge_routes
    app = FastAPI()
    register_bridge_routes(app)
    with patch("factory.api.runtime.bridge._get_aggregator", return_value=None), \
         patch("factory.api.runtime.bridge.get_tool_map", return_value=mock_tool_map), \
         patch("factory.api.runtime.bridge._get_mcp_server", return_value=MagicMock()):
        resp = TestClient(app).get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"
