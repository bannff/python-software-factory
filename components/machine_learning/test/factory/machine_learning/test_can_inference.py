"""Digest-bound LightGBM inference bridge tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

joblib = pytest.importorskip("joblib")

from factory.machine_learning.runtime.adapters.can_inference import CanInferenceBridge  # noqa: E402
from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract  # noqa: E402
from factory.mcp_utils.interface import get_service, set_service  # noqa: E402

from .can_contract_fixtures import contract, install_dataset_invoker  # noqa: E402
from .lightgbm_passport_subprocess_support import create_legacy_joblib  # noqa: E402


def _records(can_id: str = "0x1") -> list[dict]:
    return [
        {"timestamp_ns": 0, "vehicle_id": "v", "arbitration_id": can_id,
         "decoded_signals": {"a": 1.0, "b": 2.0}, "is_failure": 0},
        {"timestamp_ns": 10_000_000, "vehicle_id": "v", "arbitration_id": can_id,
         "decoded_signals": {"a": 2.0, "b": 3.0}, "is_failure": 0},
        {"timestamp_ns": 20_000_000, "vehicle_id": "v", "arbitration_id": can_id,
         "decoded_signals": {"a": 3.0, "b": 4.0}, "is_failure": 1},
    ]


@pytest.fixture
def bridge(tmp_path: Path):
    rng = np.random.default_rng(4)
    X = rng.normal(size=(80, 4)).astype(np.float32)
    y = (X[:, 0] + X[:, 3] > 0).astype(int)
    model_path = tmp_path / "model.joblib"
    create_legacy_joblib(model_path, X, y)
    feature_contract = contract(tmp_path)
    uri = save_can_feature_contract(feature_contract, tmp_path / "contract.json")
    previous = get_service("tool_invoker")
    set_service("tool_invoker", install_dataset_invoker(tmp_path))
    value = CanInferenceBridge(
        model_id="m", model_path=str(model_path),
        model_digest=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        model_type="lightgbm", loader_id="joblib", contract_uri=uri,
        contract_digest=feature_contract.digest, can_id="0x1",
        required_shape=(2, 2), required_width=4,
    )
    yield value, feature_contract
    set_service("tool_invoker", previous)


def test_prediction_is_typed_and_bound(bridge) -> None:
    value, feature_contract = bridge
    result = value.predict_window(_records(), request_digest=feature_contract.digest)
    assert result.status == "ok" and result.contract_digest == feature_contract.digest
    assert result.can_id == "0x1" and result.input_shape == (1, 4)
    assert 0 <= result.anomaly_score <= 1
    assert result.prediction in {"normal", "anomaly"}
    assert result.alert_level in {"normal", "warning", "critical"}
    assert list(result.top_signals) == sorted(
        result.top_signals, key=lambda item: item["importance"], reverse=True,
    )[:5]


@pytest.mark.parametrize("records,digest,message", [
    ([], "valid", "non-empty"),
    (_records(), "bad", "digests"),
    (_records("0x9"), "valid", "different CAN-ID"),
])
def test_mismatch_fails_without_score(bridge, records, digest, message) -> None:
    value, feature_contract = bridge
    request_digest = feature_contract.digest if digest == "valid" else "f" * 64
    with pytest.raises(ValueError, match=message):
        value.predict_window(records, request_digest=request_digest)


def test_model_digest_and_family_fail_before_load(tmp_path: Path) -> None:
    model_path = tmp_path / "model.joblib"
    joblib.dump({"not": "a model"}, model_path)
    feature_contract = contract(tmp_path)
    uri = save_can_feature_contract(feature_contract, tmp_path / "contract.json")
    base = dict(
        model_id="m", model_path=str(model_path), model_type="lightgbm",
        loader_id="joblib", contract_uri=uri, contract_digest=feature_contract.digest,
        can_id="0x1", required_shape=(2, 2), required_width=4,
    )
    with pytest.raises(ValueError, match="digest mismatch"):
        CanInferenceBridge(**base, model_digest="f" * 64)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="LightGBM model"):
        CanInferenceBridge(**base, model_digest=digest)


def test_exact_threshold_tie_follows_sealed_class_zero_rule(bridge) -> None:
    value, feature_contract = bridge
    value._score = lambda _values: value.threshold
    result = value.predict_window(_records(), request_digest=feature_contract.digest)
    assert result.anomaly_score == value.threshold
    assert result.prediction == "normal"
