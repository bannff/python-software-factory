"""Typed-envelope coverage for the time-series and CAN pipeline MCP tools."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_utils.interface import SchemaMigrationError
from factory.machine_learning.interface import TrackingRuntime, create_server


def _tool(name: str):
    return asyncio.run(create_server(TrackingRuntime()).get_tool(name)).fn


def test_time_series_input_rejects_unknown_fields() -> None:
    with pytest.raises(SchemaMigrationError, match="Extra inputs"):
        _tool("ml_predict_timeseries")(
            model_id="model", X_uri="file:///features.npy", unexpected=True,
        )


def test_invalid_time_series_family_is_a_failed_envelope() -> None:
    result = _tool("ml_train_timeseries")(
        model_type="unknown", X_uri="file:///features.npy", y_uri="file:///labels.npy",
    )
    assert result.ok is False
    assert result.data is None
    assert result.error


def test_can_pipeline_top_level_error_is_a_failed_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "factory.machine_learning.mcp.can_pipeline_tool.run_keystone_pipeline",
        lambda **_kwargs: {"error": "preflight failed", "stage": "preflight"},
    )
    result = _tool("can_run_full_pipeline")(mf4_dir="captures", dbc_path="bus.dbc")
    assert result.ok is False
    assert result.data is None
    assert result.error == "preflight failed"
