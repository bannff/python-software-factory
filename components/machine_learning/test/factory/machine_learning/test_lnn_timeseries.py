"""Liquid Neural Network (LTC) — unit + integration tests.

Mirrors the pattern of :mod:`test_torch_timeseries` so the
``torch_timeseries`` invariants (training completes, predict returns
a file URI, registry round-trips) are enforced for the LNN adapter
too. Synthetic data carries a learnable binary label so the LTC
cell has something to fit on the small window size.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")
pytest.importorskip("ncps.torch", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters.lnn_models import (  # noqa: E402
    LNNClassifier,
)
from factory.machine_learning.runtime.adapters.lnn_timeseries import (  # noqa: E402
    LnnTimeSeriesAdapter,
)
from factory.machine_learning.runtime.ports import (  # noqa: E402
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
)


@pytest.fixture
def adapter(tmp_path: Path) -> LnnTimeSeriesAdapter:
    a = LnnTimeSeriesAdapter()
    a._root = tmp_path / "models"
    a._root.mkdir(parents=True, exist_ok=True)
    return a


@pytest.fixture
def sequence_data(tmp_path: Path) -> tuple[str, str, str]:
    """Build sequences, labels, and an exact positive elapsed-time plane."""
    rng = np.random.default_rng(42)
    n_samples, n_timesteps, n_features = 100, 50, 5
    X = rng.normal(size=(n_samples, n_timesteps, n_features)).astype(np.float32)
    y = (X[:, :, 0].mean(axis=1) > 0).astype(np.int64)
    timespans = rng.uniform(1.0, 50.0, size=(n_samples, n_timesteps))
    X_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    timespans_path = tmp_path / "timespans.npy"
    np.save(X_path, X)
    np.save(y_path, y)
    np.save(timespans_path, timespans)
    return str(X_path), str(y_path), str(timespans_path)


def _small_config(**overrides: Any) -> TimeSeriesTrainingConfig:
    """Build a config that finishes in a few seconds on CPU."""
    base = dict(window_size=50, batch_size=16, epochs=2, early_stopping_patience=2)
    base.update(overrides)
    return TimeSeriesTrainingConfig(**base)


def _timing_config(uri: str) -> TimeSeriesModelConfig:
    return TimeSeriesModelConfig(auxiliary_uris={"timespans": uri})


class TestLnnAdapter:
    """End-to-end LNN adapter on synthetic sequence data."""

    def test_train_completes_with_metrics(
        self, adapter: LnnTimeSeriesAdapter, sequence_data: tuple[str, str, str],
    ) -> None:
        X_uri, y_uri, timespans_uri = sequence_data
        job = adapter.train(
            TimeSeriesModelType.lnn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(), model_config=_timing_config(timespans_uri),
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.lnn
        assert {"accuracy", "precision", "recall", "f1"} <= set(job.metrics)
        assert job.model_path and Path(job.model_path).exists()

    def test_predict_returns_file_uri(
        self, adapter: LnnTimeSeriesAdapter, sequence_data: tuple[str, str, str],
    ) -> None:
        X_uri, y_uri, timespans_uri = sequence_data
        job = adapter.train(
            TimeSeriesModelType.lnn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(), model_config=_timing_config(timespans_uri),
        )
        pred_uri = adapter.predict(job.id, X_uri)
        assert pred_uri.startswith("file://")
        payload = np.load(pred_uri.removeprefix("file://"))
        assert payload["y_pred"].shape == (100,)
        assert payload["y_score"].shape == (100,)

    def test_list_models_after_training(
        self, adapter: LnnTimeSeriesAdapter, sequence_data: tuple[str, str, str],
    ) -> None:
        X_uri, y_uri, timespans_uri = sequence_data
        adapter.train(
            TimeSeriesModelType.lnn, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(), model_config=_timing_config(timespans_uri),
        )
        models = adapter.list_models()
        assert len(models) == 1
        assert models[0]["model_type"] == "lnn"
        assert "auroc" in models[0]

    def test_predict_unknown_model_raises(self, adapter: LnnTimeSeriesAdapter) -> None:
        with pytest.raises(KeyError):
            adapter.predict("nonexistent-id", "file:///tmp/X.npy")

    def test_unsupported_model_type_raises(
        self, adapter: LnnTimeSeriesAdapter, sequence_data: tuple[str, str, str],
    ) -> None:
        X_uri, y_uri, timespans_uri = sequence_data
        with pytest.raises(NotImplementedError):
            adapter.train(TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri)


class TestLnnModelShape:
    """Sanity-check the LNN model (real ``ncps.torch.LTC``) on the CAN-shaped input."""

    def test_ltc_layer_forward_shape(self) -> None:
        """The real ``ncps.torch.LTC`` cell used inside LNNClassifier."""
        import torch
        from ncps.torch import LTC
        cell = LTC(10, 8, return_sequences=True, batch_first=True)
        x = torch.randn(4, 12, 10)
        out, hidden = cell(x)
        assert out.shape == (4, 12, 8)
        assert hidden.shape == (4, 8)

    def test_lnn_classifier_forward_shape(self) -> None:
        import torch
        model = LNNClassifier(input_size=60, hidden_size=16, n_layers=1, num_classes=2)
        x = torch.randn(8, 50, 60)
        out = model(x, torch.ones(8, 50))
        assert out.shape == (8, 2)

    def test_lnn_rejects_zero_layers(self) -> None:
        with pytest.raises(ValueError, match="n_layers must be >= 1"):
            LNNClassifier(input_size=10, hidden_size=8, n_layers=0)
