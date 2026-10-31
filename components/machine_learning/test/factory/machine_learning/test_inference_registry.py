"""LightGBM/joblib registry binding and MCP result tests."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import joblib
import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract
from factory.machine_learning.runtime.passport_store_models import ModelPassportRef
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_mcp_server

from .can_contract_fixtures import contract
from .lightgbm_passport_subprocess_support import create_legacy_joblib
from .passport_fixtures import passport


@pytest.fixture
def binding(tmp_path: Path):
    rng = np.random.default_rng(2)
    X = rng.normal(size=(40, 4)).astype(np.float32)
    y = np.asarray([0, 1] * 20)
    path = tmp_path / "model.joblib"
    create_legacy_joblib(path, X, y)
    feature_contract = contract(tmp_path)
    uri = save_can_feature_contract(feature_contract, tmp_path / "contract.json")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, feature_contract, uri


def _register(
    runtime: TrackingRuntime, binding, model_id="m", threshold=0.5, **passport_binding,
):
    path, digest, feature_contract, uri = binding
    runtime.register_inference_model(
        model_id, str(path), can_id="0x1", contract_uri=uri,
        contract_digest=feature_contract.digest, model_type="lightgbm",
        loader_id="joblib", model_digest=digest, threshold=threshold,
        required_shape=(2, 2), required_width=4, **passport_binding,
    )
    return feature_contract


def _records() -> list[dict]:
    return [
        {"timestamp_ns": ts, "arbitration_id": "0x1", "vehicle_id": "v",
         "decoded_signals": {"a": 1.0, "b": 2.0}, "is_failure": i == 2}
        for i, ts in enumerate((0, 10_000_000, 20_000_000))
    ]


def test_exact_binding_is_digest_cached_and_exposed(binding) -> None:
    runtime = TrackingRuntime()
    feature_contract = _register(runtime, binding, threshold=0.4)
    first = runtime.get_inference_bridge("m")
    assert runtime.get_inference_bridge("m") is first
    assert ("m", feature_contract.digest, binding[1]) in runtime._inference_bridges
    info = runtime.get_inference_model_info("m")
    assert info and info["model_digest"] == binding[1]
    assert info["model_type"] == "lightgbm" and info["loader_id"] == "joblib"
    assert info["required_shape"] == [2, 2] and info["required_width"] == 4


def test_reregistration_busts_cache(binding) -> None:
    runtime = TrackingRuntime()
    _register(runtime, binding, threshold=0.4)
    first = runtime.get_inference_bridge("m")
    _register(runtime, binding, threshold=0.9)
    assert runtime.get_inference_bridge("m") is not first


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    model_type=st.text(min_size=1).filter(lambda value: value != "lightgbm"),
    loader=st.text(min_size=1),
)
def test_arbitrary_non_lightgbm_registration_is_rejected(binding, model_type, loader) -> None:
    runtime = TrackingRuntime()
    with pytest.raises(ValueError, match="only LightGBM/joblib"):
        runtime.register_inference_model(
            "bad", str(binding[0]), can_id="0x1", contract_uri=binding[3],
            contract_digest=binding[2].digest, model_type=model_type,
            loader_id=loader, model_digest=binding[1],
            required_shape=(2, 2), required_width=4,
        )


def test_loader_width_and_model_digest_fail_closed(binding, tmp_path: Path) -> None:
    runtime = TrackingRuntime()
    with pytest.raises(ValueError, match="only LightGBM/joblib"):
        runtime.register_inference_model(
            "loader", str(binding[0]), can_id="0x1", contract_uri=binding[3],
            contract_digest=binding[2].digest, model_type="lightgbm", loader_id="torch",
            model_digest=binding[1], required_shape=(2, 2), required_width=4,
        )
    with pytest.raises(ValueError, match="required_width"):
        runtime.register_inference_model(
            "width", str(binding[0]), can_id="0x1", contract_uri=binding[3],
            contract_digest=binding[2].digest, model_type="lightgbm", loader_id="joblib",
            model_digest=binding[1], required_shape=(2, 2), required_width=2,
        )
    _register(runtime, binding)
    binding[0].write_bytes(b"tampered")
    with pytest.raises(ValueError, match="model artifact digest"):
        runtime.get_inference_bridge("m")


def test_candidate_passport_is_denied_by_public_mcp_without_scoring(
    binding, tmp_path: Path,
) -> None:
    candidate = passport(tmp_path, model_id="m")
    ref = ModelPassportRef(
        model_id="m", model_version="1", passport_revision=1,
        uri=(tmp_path / "passport.json").as_uri(), digest=candidate.passport_digest,
    )

    class Service:
        def get(self, requested):
            assert requested == ref
            return candidate

    runtime = TrackingRuntime(passport_service=Service())
    feature_contract = _register(
        runtime, binding, passport_ref=ref.model_dump(mode="json"),
        passport_root=str(tmp_path), prepared_x_digest=candidate.preparation.x.digest,
        prepared_y_digest=candidate.preparation.y.digest,
        materializer_config_digest=candidate.preparation.materializer.config_digest,
        inference_adapter=candidate.inference.adapter,
        inference_version=candidate.inference.version,
    )
    tool = asyncio.run(create_mcp_server(runtime=runtime).get_tool(
        "can_predict_failure_warm_compat"
    ))
    result = tool.fn(
        records=_records(), model_id="m", contract_digest=feature_contract.digest,
    )
    assert not result.ok and result.data is None
    assert "exact passport" in result.error
    missing = tool.fn(
        records=_records(), model_id="missing", contract_digest=feature_contract.digest,
    )
    assert not missing.ok and missing.data is None
    assert "not registered" in missing.error
