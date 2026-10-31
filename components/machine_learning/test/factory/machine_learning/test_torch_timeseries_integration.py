"""Integration test: LSTM and TCN on synthetic CAN-like time-series data.

Verifies end-to-end training, metric validity, and prediction correctness
on 100 samples × 50 timesteps × 10 features — the shape expected from the
CAN failure-prediction pipeline.
"""

from __future__ import annotations

from pathlib import Path

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter(tmp_path: Path) -> TorchTimeSeriesAdapter:
    """Fresh adapter backed by a per-test durable model directory."""
    return TorchTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=tmp_path / "models",
    )


@pytest.fixture
def can_data(tmp_path: Path) -> tuple[str, str]:
    """Synthetic CAN-like data: 100 samples, 50 timesteps, 10 features.

    A learnable binary signal is baked into feature-0 so models have
    something non-trivial to fit.
    """
    rng = np.random.default_rng(42)
    n_samples, n_timesteps, n_features = 100, 50, 10
    X = rng.normal(size=(n_samples, n_timesteps, n_features)).astype(np.float32)
    # Positive mean of feature-0 across the window → label 1
    y = (X[:, :, 0].mean(axis=1) > 0).astype(np.int64)
    X_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(X_path, X)
    np.save(y_path, y)
    return str(X_path), str(y_path)


def _quick_config() -> TimeSeriesTrainingConfig:
    """Config that finishes fast on CPU — 3 epochs, small batch."""
    return TimeSeriesTrainingConfig(
        window_size=50,
        batch_size=16,
        epochs=3,
        early_stopping_patience=2,
        learning_rate=1e-3,
        seed=42,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTorchTimeseriesIntegration:
    """Full integration tests for LSTM and TCN on CAN-shaped data."""

    def test_lstm_trains_and_predicts(self, adapter: TorchTimeSeriesAdapter, can_data: tuple[str, str]) -> None:
        """LSTM: train → metrics → predict → valid output."""
        X_uri, y_uri = can_data
        cfg = _quick_config()

        # Train
        job = adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri,
            config=cfg, experiment_name="integ-lstm",
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.lstm
        assert Path(job.model_path).exists()

        # Metrics must be present and finite
        for key in ("accuracy", "precision", "recall", "f1"):
            assert key in job.metrics, f"missing metric: {key}"
            assert np.isfinite(job.metrics[key]), f"{key} is not finite"

        # Predict
        pred_uri = adapter.predict(job.id, X_uri)
        assert pred_uri.startswith("file://")
        payload = np.load(pred_uri.removeprefix("file://"))
        y_pred = payload["y_pred"]
        y_score = payload["y_score"]
        assert y_pred.shape == (100,), f"unexpected y_pred shape: {y_pred.shape}"
        assert y_score.shape == (100,), f"unexpected y_score shape: {y_score.shape}"
        assert not np.any(np.isnan(y_pred)), "y_pred contains NaN"
        assert not np.any(np.isnan(y_score)), "y_score contains NaN"
        assert set(np.unique(y_pred)).issubset({0, 1}), f"unexpected labels: {np.unique(y_pred)}"

    def test_tcn_trains_and_predicts(self, adapter: TorchTimeSeriesAdapter, can_data: tuple[str, str]) -> None:
        """TCN: train → metrics → predict → valid output."""
        X_uri, y_uri = can_data
        cfg = _quick_config()

        # Train
        job = adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri,
            config=cfg, experiment_name="integ-tcn",
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.tcn
        assert Path(job.model_path).exists()

        # Metrics must be present and finite
        for key in ("accuracy", "precision", "recall", "f1"):
            assert key in job.metrics, f"missing metric: {key}"
            assert np.isfinite(job.metrics[key]), f"{key} is not finite"

        # Predict
        pred_uri = adapter.predict(job.id, X_uri)
        assert pred_uri.startswith("file://")
        payload = np.load(pred_uri.removeprefix("file://"))
        y_pred = payload["y_pred"]
        y_score = payload["y_score"]
        assert y_pred.shape == (100,)
        assert y_score.shape == (100,)
        assert not np.any(np.isnan(y_pred)), "y_pred contains NaN"
        assert not np.any(np.isnan(y_score)), "y_score contains NaN"
        assert set(np.unique(y_pred)).issubset({0, 1})

    def test_both_models_agree_on_shape(self, adapter: TorchTimeSeriesAdapter, can_data: tuple[str, str]) -> None:
        """LSTM and TCN produce identically shaped predictions on the same data."""
        X_uri, y_uri = can_data
        cfg = _quick_config()

        lstm_job = adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri, config=cfg,
        )
        tcn_job = adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri, config=cfg,
        )

        lstm_pred = np.load(adapter.predict(lstm_job.id, X_uri).removeprefix("file://"))
        tcn_pred = np.load(adapter.predict(tcn_job.id, X_uri).removeprefix("file://"))
        assert lstm_pred["y_pred"].shape == tcn_pred["y_pred"].shape
        assert lstm_pred["y_score"].shape == tcn_pred["y_score"].shape

    def test_compare_models_after_training(
        self, adapter: TorchTimeSeriesAdapter, can_data: tuple[str, str],
    ) -> None:
        """compare_models ranks LSTM and TCN on a shared metric."""
        X_uri, y_uri = can_data
        cfg = _quick_config()
        lstm_job = adapter.train(
            TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri, config=cfg,
        )
        tcn_job = adapter.train(
            TimeSeriesModelType.tcn, X_uri=X_uri, y_uri=y_uri, config=cfg,
        )
        result = adapter.compare_models([lstm_job.id, tcn_job.id], metric="accuracy")
        assert result["count"] == 2
        assert result["best_model_id"] in {lstm_job.id, tcn_job.id}
        # Sorted descending by accuracy
        assert result["models"][0]["accuracy"] >= result["models"][1]["accuracy"]
