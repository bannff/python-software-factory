"""Inference MCP sequencing and typed fail-closed envelopes."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import numpy as np
import pytest

from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import get_service, set_service

from .can_contract_fixtures import contract, install_dataset_invoker
from .lightgbm_passport_subprocess_support import create_legacy_joblib


def _records() -> list[dict]:
    return [
        {"timestamp_ns": ts, "arbitration_id": "0x1", "vehicle_id": "v",
         "decoded_signals": {"a": float(i + 1), "b": float(i + 2)},
         "is_failure": i == 2}
        for i, ts in enumerate((0, 10_000_000, 20_000_000))
    ]


def _setup(tmp_path: Path):
    feature_contract = contract(tmp_path)
    uri = save_can_feature_contract(feature_contract, tmp_path / "contract.json")
    X = np.asarray([[0, 0, 0, 0], [1, 2, 2, 3], [2, 1, 3, 2], [5, 5, 5, 5]])
    y = np.asarray([0, 0, 1, 1])
    path = tmp_path / "model.joblib"
    create_legacy_joblib(path, X, y)
    runtime = TrackingRuntime()
    runtime.register_inference_model(
        "m", str(path), can_id="0x1", contract_uri=uri,
        contract_digest=feature_contract.digest, model_type="lightgbm",
        loader_id="joblib", model_digest=hashlib.sha256(path.read_bytes()).hexdigest(),
        required_shape=(2, 2), required_width=4,
    )
    return runtime, feature_contract


def test_inference_uses_submit_status_artifact_with_v2_refs(tmp_path: Path) -> None:
    runtime, feature_contract = _setup(tmp_path)
    calls: list[tuple[str, dict]] = []
    previous = get_service("tool_invoker")
    set_service("tool_invoker", install_dataset_invoker(tmp_path, calls))
    try:
        result = runtime.get_inference_bridge("m").predict_window(
            _records(), request_digest=feature_contract.digest,
        )
    finally:
        set_service("tool_invoker", previous)
    assert result.status == "ok"
    assert [name for name, _ in calls] == [
        "dataset_submit_generation", "dataset_get_job", "dataset_get_artifact",
    ]
    submit = calls[0][1]
    assert submit["recipe_uri"] == "recipe://local/can-window@2"
    assert submit["input_artifact_roles"] == [
        "primary_dataset", "prior_data_policy", "signal_schema:0x1",
    ]
    assert len(submit["input_artifact_digests"]) == 3


def test_unpassported_model_returns_typed_denial_without_prediction(
    tmp_path: Path,
) -> None:
    runtime, _ = _setup(tmp_path)
    tool = asyncio.run(create_mcp_server(runtime=runtime).get_tool(
        "can_predict_failure_warm_compat"
    ))
    result = tool.fn(records=_records(), model_id="m", contract_digest="f" * 64)
    assert not result.ok and result.data is None
    assert "exact registered passport" in result.error
