"""Torch time-series adapter — training, inference, and registry tests.

Synthetic data is generated with a learnable signal baked into a single
feature so the LSTM / TCN models have something nontrivial to fit on the
small window size used in the test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker  # noqa: E402
from factory.machine_learning.runtime.adapters.torch_timeseries import (  # noqa: E402
    TorchTimeSeriesAdapter,
)
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelType, TimeSeriesTrainingConfig,
)


@pytest.fixture
def adapter(tmp_path: Path) -> TorchTimeSeriesAdapter:
    return TorchTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=tmp_path / "models",
    )


@pytest.fixture
def sequence_data(tmp_path: Path) -> tuple[str, str]:
    """Build (100, 20, 5) sequences with a learnable binary label and persist."""
    rng = np.random.default_rng(42)
    n_samples, n_timesteps, n_features = 100, 20, 5
    X = rng.normal(size=(n_samples, n_timesteps, n_features)).astype(np.float32)
    # Signal: positive mean of feature 0 across the window -> label 1.
    y = (X[:, :, 0].mean(axis=1) > 0).astype(np.int64)
    X_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(X_path, X)
    np.save(y_path, y)
    return str(X_path), str(y_path)


def _small_config(**overrides: Any) -> TimeSeriesTrainingConfig:
    """Build a config that finishes in a few seconds on CPU."""
    base = dict(window_size=20, batch_size=16, epochs=3, early_stopping_patience=2)
    base.update(overrides)
    return TimeSeriesTrainingConfig(**base)


class TestTorchTimeSeriesAdapter:
    """Verify the PyTorch adapter end-to-end on synthetic sequence data."""

    def test_lstm_train_completes_with_metrics(
        self, adapter: TorchTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        """LSTM training yields a completed job with on-disk model + metrics."""
        X_uri, y_uri = sequence_data
        job = adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(), experiment_name="torch-lstm",
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.lstm
        assert {"accuracy", "precision", "recall", "f1"} <= set(job.metrics)
        assert job.model_path and Path(job.model_path).exists()

    def test_tcn_train_completes_with_metrics(
        self, adapter: TorchTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        """TCN training yields a completed job with on-disk model + metrics."""
        X_uri, y_uri = sequence_data
        job = adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.tcn
        assert {"accuracy", "precision", "recall", "f1"} <= set(job.metrics)
        assert job.model_path and Path(job.model_path).exists()

    def test_predict_returns_file_uri(
        self, adapter: TorchTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        """predict returns a file:// URI pointing to a .npz of predictions."""
        X_uri, y_uri = sequence_data
        lstm = adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        tcn = adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        for job in (lstm, tcn):
            pred_uri = adapter.predict(job.id, X_uri)
            assert pred_uri.startswith("file://")
            payload = np.load(pred_uri.removeprefix("file://"))
            assert payload["y_pred"].shape == (100,)
            assert payload["y_score"].shape == (100,)

    def test_list_models_after_training(
        self, adapter: TorchTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        """list_models returns one summary per trained model."""
        X_uri, y_uri = sequence_data
        adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        models = adapter.list_models()
        assert len(models) == 2
        types = {m["model_type"] for m in models}
        assert types == {"lstm", "tcn"}
        assert all("auroc" in m for m in models)

    def test_predict_unknown_model_raises(self, adapter: TorchTimeSeriesAdapter) -> None:
        """predict must raise KeyError for missing model ids."""
        with pytest.raises(KeyError):
            adapter.predict("nonexistent-id", "file:///tmp/X.npy")

    def test_unsupported_model_type_raises(
        self, adapter: TorchTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        """LightGBM and PatchTST are NOT supported by the torch adapter."""
        X_uri, y_uri = sequence_data
        for model_type in (TimeSeriesModelType.lightgbm, TimeSeriesModelType.patchtst):
            with pytest.raises(NotImplementedError):
                adapter.train(model_type, X_uri=X_uri, y_uri=y_uri)

    def test_train_logs_to_tracker(
        self, tmp_path: Path, sequence_data: tuple[str, str],
    ) -> None:
        """Tracker receives the run with params + metrics after training."""
        tracker = MemoryTracker()
        a = TorchTimeSeriesAdapter(
            tracker=tracker, model_root=tmp_path / "models",
        )
        X_uri, y_uri = sequence_data
        job = a.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(), experiment_name="torch-tracker",
        )
        assert job.run_id is not None
        run = tracker.get_run(job.run_id)
        assert run is not None
        assert run.params["model_type"] == "lstm"
        assert run.metrics.get("accuracy") is not None

    def test_compare_models_picks_best(
        self, adapter: TorchTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        """compare_models ranks registered models on a single metric."""
        X_uri, y_uri = sequence_data
        lstm = adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        tcn = adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        result = adapter.compare_models([lstm.id, tcn.id], metric="accuracy")
        assert result["count"] == 2
        assert {r["id"] for r in result["models"]} == {lstm.id, tcn.id}
        assert result["models"][0]["accuracy"] >= result["models"][1]["accuracy"]


