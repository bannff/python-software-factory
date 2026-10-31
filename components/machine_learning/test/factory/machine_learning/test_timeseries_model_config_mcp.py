"""Focused MCP tests for strict per-family time-series model configuration."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from factory.mcp_utils.interface import SchemaMigrationError
from factory.machine_learning.interface import TrackingRuntime, create_server
from factory.machine_learning.runtime.time_series_ports import TimeSeriesTrainingConfig
from factory.machine_learning.server import get_mcp_server


def _tool(name: str):
    return asyncio.run(get_mcp_server().get_tool(name))


def _referenced_schema(schema: dict[str, Any], field: str) -> dict[str, Any]:
    branch = next(item for item in schema["properties"][field]["anyOf"] if "$ref" in item)
    return schema["$defs"][branch["$ref"].rsplit("/", 1)[-1]]


class TestPublicTimeSeriesConfig:
    """The public tool rejects invalid config and forwards valid typed config."""

    def test_model_config_schema_is_closed_and_discoverable(self) -> None:
        schema = _tool("ml_train_timeseries").fn._mcp_input_model.model_json_schema(
            mode="validation"
        )
        model_schema = _referenced_schema(schema, "model_config")
        assert model_schema["additionalProperties"] is False
        assert set(model_schema["properties"]) == {
            "auxiliary_uris", "local_backbone_ref", "lora", "lora_config",
        }
        assert not any(
            branch.get("additionalProperties") is True
            for branch in schema["properties"]["model_config"]["anyOf"]
        )

    def test_prior_family_rejects_non_null_model_config(self) -> None:
        result = _tool("ml_train_timeseries").fn(
            model_type="lightgbm", X_uri="file:///unused-X", y_uri="file:///unused-y",
            model_config={"auxiliary_uris": {}},
        )
        assert not result.ok
        assert "model_config is not supported by lightgbm" in result.error

    @pytest.mark.parametrize(("model_type", "model_config", "message"), [
        ("lnn", {"auxiliary_uris": {"unexpected": "file:///x"}},
         "only accepts the timespans URI"),
        ("lnn", {"lora": "false"}, "Input should be a valid boolean"),
    ])
    def test_malformed_model_config_is_an_error_envelope(
        self, model_type: str, model_config: dict[str, object], message: str,
    ) -> None:
        if model_config == {"lora": "false"}:
            with pytest.raises(SchemaMigrationError, match=message):
                _tool("ml_train_timeseries").fn(
                    model_type=model_type, X_uri="file:///unused-X", y_uri="file:///unused-y",
                    model_config=model_config,
                )
            return
        result = _tool("ml_train_timeseries").fn(
            model_type=model_type, X_uri="file:///unused-X", y_uri="file:///unused-y",
            model_config=model_config,
        )
        assert not result.ok
        assert result.error is not None
        assert message in result.error

    def test_valid_model_config_is_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, Any] = {}
        runtime = TrackingRuntime()

        def train(**kwargs: Any) -> SimpleNamespace:
            seen.update(kwargs)
            return SimpleNamespace(
                id="job", model_type=kwargs["model_type"], status="completed",
                experiment_id=None, run_id=None, metrics={}, model_path=None,
            )

        monkeypatch.setattr(
            runtime, "get_timeseries_trainer", lambda: SimpleNamespace(train=train),
        )
        monkeypatch.setattr(
            "factory.machine_learning.mcp.timeseries_tools.persist_training_run",
            lambda *_args, **_kwargs: None,
        )
        server = create_server(runtime)
        tool_result = asyncio.run(server.call_tool("ml_train_timeseries", {
            "model_type": "lnn", "X_uri": "file:///X", "y_uri": "file:///y",
            "model_config": {
                "auxiliary_uris": {"timespans": "file:///times.npy"},
            },
        }))
        assert tool_result.structured_content["ok"] is True
        assert tool_result.structured_content["data"]["status"] == "completed"
        assert type(seen["config"]) is TimeSeriesTrainingConfig
        assert seen["model_config"].auxiliary_uris == {"timespans": "file:///times.npy"}
