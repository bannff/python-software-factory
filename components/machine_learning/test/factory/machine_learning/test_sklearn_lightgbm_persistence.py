"""Exact native-Booster MLflow persistence without native parent imports."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
import sys

import numpy as np
import pytest
import yaml

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker
from factory.machine_learning.runtime.adapters.mlflow_lightgbm import load_lightgbm_flavor
from factory.machine_learning.runtime.adapters.sklearn_timeseries import SklearnTimeSeriesAdapter
from factory.machine_learning.runtime.adapters.temporal_split import temporal_split_with_shuffle_fallback
from factory.machine_learning.runtime.ports import TimeSeriesModelType

_EXPECTED_FILES = {
    "MLmodel", "conda.yaml", "model.lgb", "python_env.yaml", "requirements.txt",
}
_EXPECTED_METADATA = {
    "schema_version": 1, "classes": [0, 1], "positive_class": 1,
    "positive_class_index": 1, "threshold": 0.5,
    "prediction_rule": "argmax_tie_to_class_0", "raw_score": False,
    "feature_width": 10, "feature_importance_type": "split",
    "iteration_semantics": "all_iterations",
}


def _data(tmp_path: Path) -> tuple[str, str, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    X = rng.normal(size=(100, 10)).astype(np.float32)
    y = (X[:, 0] > 0).astype(int)
    x_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(x_path, X); np.save(y_path, y)
    return str(x_path), str(y_path), X, y


def _train(tmp_path: Path):
    x_uri, y_uri, X, y = _data(tmp_path)
    adapter = SklearnTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=tmp_path / "models",
    )
    job = adapter.train(TimeSeriesModelType.lightgbm, x_uri, y_uri)
    return adapter, job, X, y


def test_native_artifact_metadata_and_cold_view_parity(tmp_path: Path) -> None:
    _, job, X, y = _train(tmp_path)
    model_path = Path(job.model_path)
    assert {item.name for item in model_path.iterdir()} == _EXPECTED_FILES
    assert (model_path / "requirements.txt").read_text() == (
        f"lightgbm=={version('lightgbm')}\nmlflow=={version('mlflow')}"
    )
    model_text = (model_path / "model.lgb").read_text()
    assert "[num_iterations: 100]" in model_text
    assert "[max_depth: 6]" in model_text and "[learning_rate: 0.1]" in model_text
    document = yaml.safe_load((model_path / "MLmodel").read_text())
    assert document["metadata"] == _EXPECTED_METADATA
    assert document["flavors"]["lightgbm"]["data"] == "model.lgb"
    assert document["flavors"]["lightgbm"]["model_class"] == "lightgbm.basic.Booster"
    _, _, validation_X, _ = temporal_split_with_shuffle_fallback(
        X, y, job.config.validation_split, job.config.seed,
    )
    cold = load_lightgbm_flavor(model_path, expected_width=10)
    np.testing.assert_array_equal(cold.classes_, np.array([0, 1]))
    np.testing.assert_array_equal(cold.predict_proba(validation_X)[:, 1], job.val_y_score)
    np.testing.assert_array_equal(cold.predict(validation_X), job.val_y_pred)
    assert cold.feature_importances_.shape == (10,)
    assert cold.n_features_in_ == 10 and cold.threshold == 0.5
    assert "lightgbm" not in sys.modules and "mlflow.lightgbm" not in sys.modules


def test_unsafe_artifact_or_metadata_is_rejected_before_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, job, _, _ = _train(tmp_path)
    model_path = Path(job.model_path)
    metadata_path = model_path / "MLmodel"
    original = yaml.safe_load(metadata_path.read_text())
    import factory.machine_learning.runtime.adapters.mlflow_lightgbm as module
    monkeypatch.setattr(
        module.BinaryBoosterClassifier, "from_mlflow",
        lambda *_args, **_kwargs: pytest.fail("invalid flavor reached native child"),
    )
    bad = yaml.safe_load(yaml.safe_dump(original))
    bad["metadata"]["feature_width"] = "10"
    metadata_path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="metadata values|feature width"):
        load_lightgbm_flavor(model_path)
    bad = yaml.safe_load(yaml.safe_dump(original))
    bad["metadata"]["unexpected"] = True
    metadata_path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="metadata fields"):
        load_lightgbm_flavor(model_path)
    metadata_path.write_text(yaml.safe_dump(original))
    (model_path / "model.skops").write_bytes(b"unsafe")
    with pytest.raises(ValueError, match="missing or extra files"):
        load_lightgbm_flavor(model_path)


def test_get_model_returns_native_flavor_directory(tmp_path: Path) -> None:
    adapter, job, _, _ = _train(tmp_path)
    record = adapter.get_model(job.id)
    assert record and record["id"] == job.id and record["model_type"] == "lightgbm"
    assert Path(record["model_path"]).is_dir() and adapter.get_model("missing") is None


def test_train_logs_to_tracker(tmp_path: Path) -> None:
    x_uri, y_uri, _, _ = _data(tmp_path)
    tracker = MemoryTracker()
    adapter = SklearnTimeSeriesAdapter(tracker=tracker, model_root=tmp_path / "models")
    job = adapter.train(
        TimeSeriesModelType.lightgbm, x_uri, y_uri,
        experiment_name="can-failure-tracker",
    )
    run = tracker.get_run(job.run_id)
    assert run and run.metrics.get("accuracy") is not None
    assert run.metrics.get("auroc") is not None and run.params["model_type"] == "lightgbm"


def test_lightgbm_requires_explicit_durable_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ML_LIGHTGBM_MODEL_ROOT", raising=False)
    x_uri, y_uri, _, _ = _data(tmp_path)
    adapter = SklearnTimeSeriesAdapter(tracker=MemoryTracker())
    with pytest.raises(ValueError, match="ML_LIGHTGBM_MODEL_ROOT"):
        adapter.train(TimeSeriesModelType.lightgbm, x_uri, y_uri)
