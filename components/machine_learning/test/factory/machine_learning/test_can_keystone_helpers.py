"""Per-CAN contract training registration-status tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from factory.machine_learning.runtime.can_contract_training import train_can_contracts
from factory.machine_learning.runtime.can_inference_gate import build_inference_gate
from factory.machine_learning.runtime.ports import TimeSeriesModelType

from .can_contract_fixtures import contract, refs, window


def test_competitors_train_but_only_lightgbm_is_warm(tmp_path: Path) -> None:
    feature_contract = contract(tmp_path)
    schema_ref, policy_ref = refs(tmp_path)
    artifact = tmp_path / "windows.jsonl"
    artifact.write_text(json.dumps(window(feature_contract)) + "\n")
    lgbm_path = tmp_path / "lgbm.joblib"
    torch_path = tmp_path / "lnn.pt"
    lgbm_path.write_bytes(b"lightgbm")
    torch_path.write_bytes(b"torch")

    def trained(_trainer, model_type, *_args, model_config=None):
        assert model_config is None
        path = lgbm_path if model_type is TimeSeriesModelType.lightgbm else torch_path
        job = SimpleNamespace(id=f"job-{model_type.value}", model_path=str(path))
        row = {"metrics": {"auroc": 0.8}, "model_type": model_type.value}
        return job, row

    runtime = MagicMock()
    with patch(
        "factory.machine_learning.runtime.can_contract_training.convert_records_to_npy",
        return_value=("file:///x.npy", "file:///y.npy", {
            "x_2d_uri": "file:///x2.npy", "x_3d_uri": "file:///x3.npy",
            "n_samples": 1, "n_features": 2, "window_size": 2,
            "label_dist": {"0": 1},
        }),
    ), patch(
        "factory.machine_learning.runtime.can_contract_training._train_one",
        side_effect=trained,
    ):
        table, live_ids = train_can_contracts(
            trainer=MagicMock(), runtime=runtime, augmented_uri=artifact.as_uri(),
            top_n=1, vehicle_id="v", snapshots_dir=tmp_path,
            model_types=[TimeSeriesModelType.lightgbm, TimeSeriesModelType.lnn],
            source_digests=["c" * 64], signal_schema_refs={"0x1": schema_ref},
            prior_data_policy_ref=policy_ref,
        )

    assert live_ids == ["job-lightgbm"]
    assert {row["registration_status"] for row in table} == {"warm", "candidate"}
    warm = next(row for row in table if row["model_type"] == "lightgbm")
    assert warm["promotion_status"] == "candidate"
    assert warm["conformance_status"] == "not_run"
    assert warm["inference_gate"] == "failed"
    candidate = next(row for row in table if row["model_type"] == "lnn")
    assert candidate["promotion_status"] == "candidate"
    assert candidate["conformance_status"] == "not_run"
    assert candidate["inference_gate"] == "failed"
    assert candidate.get("error_code") is None
    assert {row["model_type"] for row in table} == {"lightgbm", "lnn"}
    runtime.register_inference_model.assert_called_once()
    kwargs = runtime.register_inference_model.call_args.kwargs
    assert (
        kwargs["model_type"] == "lightgbm"
        and kwargs["loader_id"] == "mlflow.lightgbm"
    )
    assert kwargs["model_digest"]


def test_requested_training_failure_is_an_explicit_failed_outcome(tmp_path: Path) -> None:
    feature_contract = contract(tmp_path)
    schema_ref, policy_ref = refs(tmp_path)
    artifact = tmp_path / "windows.jsonl"
    artifact.write_text(json.dumps(window(feature_contract)) + "\n")
    info = {
        "x_2d_uri": "file:///x2.npy", "x_3d_uri": "file:///x3.npy",
        "n_samples": 1, "n_features": 2, "window_size": 2,
        "label_dist": {"0": 1},
    }
    with patch(
        "factory.machine_learning.runtime.can_contract_training.convert_records_to_npy",
        return_value=("file:///x.npy", "file:///y.npy", info),
    ), patch(
        "factory.machine_learning.runtime.can_contract_training._train_one",
        return_value=(None, None),
    ):
        table, live_ids = train_can_contracts(
            trainer=MagicMock(), runtime=MagicMock(), augmented_uri=artifact.as_uri(),
            top_n=1, vehicle_id="v", snapshots_dir=tmp_path,
            model_types=[TimeSeriesModelType.lightgbm], source_digests=["c" * 64],
            signal_schema_refs={"0x1": schema_ref},
            prior_data_policy_ref=policy_ref,
        )
    assert live_ids == []
    assert table[0]["inference_gate"] == "failed"
    assert table[0]["error_code"] == "training_failed"


def _post_training_failure(
    tmp_path: Path, model_path: Path, registration_error: Exception | None = None,
) -> tuple[list[dict], list[str]]:
    feature_contract = contract(tmp_path)
    schema_ref, policy_ref = refs(tmp_path)
    artifact = tmp_path / "failure-windows.jsonl"
    artifact.write_text(json.dumps(window(feature_contract)) + "\n")
    info = {
        "x_2d_uri": "file:///x2.npy", "x_3d_uri": "file:///x3.npy",
        "n_samples": 1, "n_features": 2, "window_size": 2,
        "label_dist": {"0": 1},
    }
    runtime = MagicMock()
    runtime.register_inference_model.side_effect = registration_error
    trained = (
        SimpleNamespace(id="job-lightgbm", model_path=str(model_path)),
        {"metrics": {"auroc": 0.8}, "model_type": "lightgbm"},
    )
    with patch(
        "factory.machine_learning.runtime.can_contract_training.convert_records_to_npy",
        return_value=("file:///x.npy", "file:///y.npy", info),
    ), patch(
        "factory.machine_learning.runtime.can_contract_training._train_one",
        return_value=trained,
    ):
        return train_can_contracts(
            trainer=MagicMock(), runtime=runtime, augmented_uri=artifact.as_uri(),
            top_n=1, vehicle_id="v", snapshots_dir=tmp_path,
            model_types=[TimeSeriesModelType.lightgbm], source_digests=["c" * 64],
            signal_schema_refs={"0x1": schema_ref},
            prior_data_policy_ref=policy_ref,
        )


def test_missing_trained_artifact_is_one_failed_outcome(tmp_path: Path) -> None:
    table, live_ids = _post_training_failure(tmp_path, tmp_path / "missing.joblib")
    assert live_ids == [] and len(table) == 1
    assert table[0]["error_code"] == "training_failed"
    assert table[0]["inference_gate"] == "failed"


def test_registration_rejection_is_one_failed_outcome(tmp_path: Path) -> None:
    model_path = tmp_path / "rejected.joblib"
    model_path.write_bytes(b"model")
    table, live_ids = _post_training_failure(
        tmp_path, model_path, RuntimeError("binding rejected"),
    )
    assert live_ids == [] and len(table) == 1
    assert table[0]["error_code"] == "training_failed"
    assert "binding rejected" in table[0]["error"]


def test_mixed_model_outcomes_fail_the_top_level_gate() -> None:
    gate = build_inference_gate([
        {"model_type": "lightgbm", "inference_gate": "passed"},
        {"model_type": "chronos", "inference_gate": "failed",
         "error_code": "inference_adapter_defect"},
    ], ["job-lightgbm"])
    assert gate == {
        "status": "failed", "error_code": "inference_adapter_defect",
        "failed_model_types": ["chronos", "lightgbm"],
        "promotable_model_ids": [], "warm_model_ids": ["job-lightgbm"],
        "live_model_ids": [],
    }
