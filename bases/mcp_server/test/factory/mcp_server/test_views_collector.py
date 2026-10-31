"""Regression #45: a view tool whose payload fails its contract must be
reported, not silently skipped behind a misleading "Collected 0 views" line.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from factory.mcp_server.runtime import views as views_mod


@pytest.fixture(autouse=True)
def _clear_view_cache():
    views_mod.invalidate_view_cache()
    yield
    views_mod.invalidate_view_cache()


def _aggregator(result):
    agg = MagicMock()
    agg.get_all_tool_names.return_value = ["demo_get_views"]
    agg.invoke_tool.return_value = result
    return agg


def test_rejected_view_payload_is_reported(caplog):
    """A failed tool envelope (``{"error": ...}``) must log a WARNING."""
    agg = _aggregator({"error": "1 validation error for ViewsOutput"})
    with caplog.at_level(logging.WARNING, logger="factory.mcp_server.runtime.views"):
        collected = views_mod.ensure_views_registered(agg)
    assert collected == {}
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "demo_get_views" in m and "validation error" in m for m in warnings
    ), warnings


def test_healthy_view_payload_logs_no_rejection(caplog):
    """Control: a list payload is collected and emits no rejection warning."""
    agg = _aggregator([{"id": "demo-view"}])
    with caplog.at_level(logging.WARNING, logger="factory.mcp_server.runtime.views"):
        collected = views_mod.ensure_views_registered(agg)
    assert "demo-view" in collected
    assert not [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "was rejected" in r.getMessage()
    ]
