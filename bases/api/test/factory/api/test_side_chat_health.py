"""`/api/health` projection of the side-chat planner state (issue #41).

The side-chat wiring deliberately never fails route registration, so a
misconfigured model used to be a silent feature loss visible only in one boot
log line (which itself hid the cause behind a traceback). These tests pin the
other half of the fix: the same reason the wiring logs is projected onto the
health payload the dashboard/scripts already read.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime.bridge import register_bridge_routes
from factory.api.runtime.side_chat_wiring import register_side_chat


def _mock_aggregator() -> MagicMock:
    """Aggregator double whose health/capabilities payloads are serializable.

    A bare ``MagicMock`` wedges this route: ``make_serializable`` calls
    ``obj.model_dump()`` on anything exposing that attribute
    (``components/mcp_utils/src/factory/mcp_utils/serialization.py:32``), a
    MagicMock exposes everything, so serialization recurses until
    ``RecursionError``. Same shape as ``test_bridge._make_mock_aggregator``.
    """
    agg = MagicMock()
    agg.get_all_tool_names.return_value = ["kb_search"]
    agg.get_aggregated_health.return_value = {"status": "healthy"}
    agg.get_aggregated_capabilities.return_value = {}
    return agg


def _health() -> dict:
    """Register the real wiring + bridge routes, then read /api/health."""
    app = FastAPI()
    with patch(
        "factory.api.runtime.views.ensure_views_registered",
    ), patch(
        "factory.api.runtime.bridge._get_aggregator",
        return_value=_mock_aggregator(),
    ), patch(
        # The planner is built during registration, and a real Bedrock client
        # would need live AWS credentials.
        "langchain_aws.ChatBedrockConverse", MagicMock(),
    ):
        register_bridge_routes(app)
        register_side_chat(app)
        return TestClient(app).get("/api/health").json()


def test_health_surfaces_a_degraded_side_chat_planner(monkeypatch):
    monkeypatch.delenv("COMPANION_X_CHAT_MODEL", raising=False)

    side_chat = _health()["side_chat"]

    assert side_chat["status"] == "unavailable"
    assert "COMPANION_X_CHAT_MODEL" in side_chat["reason"]


def test_health_reports_a_ready_side_chat_planner(monkeypatch):
    monkeypatch.setenv("COMPANION_X_CHAT_MODEL", "us.anthropic.claude-sonnet-4-6")

    side_chat = _health()["side_chat"]

    assert side_chat == {
        "status": "ready", "model_id": "us.anthropic.claude-sonnet-4-6",
    }
