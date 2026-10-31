"""Telemetry readiness gating for aggregated MCP startup."""
from __future__ import annotations

import pytest

from factory.mcp_server.core import _initialize_telemetry


def test_companion_x_telemetry_gate_fails_loud(monkeypatch) -> None:
    aggregator = type("Aggregator", (), {
        "get_brick_tools": lambda self, name: [],
    })()
    monkeypatch.setattr(
        "factory.telemetry.interface.health_check",
        lambda: {"ok": False, "error": "exporter unavailable"},
    )

    with pytest.raises(RuntimeError, match="requires healthy Telemetry"):
        _initialize_telemetry(aggregator, required=True)


def test_unrelated_project_telemetry_gate_is_best_effort() -> None:
    aggregator = type("Aggregator", (), {
        "get_brick_tools": lambda self, name: (_ for _ in ()).throw(
            RuntimeError("not configured")
        ),
    })()

    _initialize_telemetry(aggregator, required=False)
