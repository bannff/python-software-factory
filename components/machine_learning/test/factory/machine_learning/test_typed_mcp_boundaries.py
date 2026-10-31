"""Focused Pydantic-v2 boundary coverage for ML tracking/fine-tuning tools."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.interface import SchemaMigrationError
from factory.machine_learning.server import create_mcp_server
from factory.machine_learning.runtime.runtime import reset_runtime


def _tool(name: str):
    reset_runtime()
    return asyncio.run(create_mcp_server().get_tool(name)).fn


def test_tracking_input_rejects_unknown_field() -> None:
    with pytest.raises(SchemaMigrationError, match="Extra inputs"):
        _tool("tracking_create_experiment")(name="run", unexpected=True)


def test_unknown_job_is_an_ordinary_successful_negative() -> None:
    result = _tool("ml_get_job_status")(job_id="missing")
    assert result.ok is True
    assert result.data.found is False


def test_runtime_failure_is_a_failed_envelope() -> None:
    result = _tool("ml_create_finetuning_job")(method="unknown", base_model="base", dataset_uri="dataset", manifest_uri="manifest", dataset_digest="digest", view_name="view", view_schema_version="v1")
    assert result.ok is False
    assert result.data is None
    assert result.error


def test_authoring_gate_is_a_failed_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ML_ENABLE_AUTHORING_TOOLS", raising=False)
    result = _tool("ml_configure_training_defaults")()
    assert result.ok is False
    assert result.data is None
    assert "disabled" in result.error.lower()
