"""LNN irregular-timing tests (bd:python-factory-q1jsr.4).

Split out of ``test_lnn_timeseries.py`` to keep both files under the
200-LOC ceiling. Covers ``LNNClassifier.forward``'s optional
``timespans`` argument and ``LnnTimeSeriesAdapter.train()``'s
``TimeSeriesModelConfig.auxiliary_uris["timespans"]`` routing end-to-end.
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
def sequence_data(tmp_path: Path) -> tuple[str, str]:
    """Build (100, 50, 5) sequences with a learnable binary label."""
    rng = np.random.default_rng(42)
    n_samples, n_timesteps, n_features = 100, 50, 5
    X = rng.normal(size=(n_samples, n_timesteps, n_features)).astype(np.float32)
    y = (X[:, :, 0].mean(axis=1) > 0).astype(np.int64)
    X_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(X_path, X)
    np.save(y_path, y)
    return str(X_path), str(y_path)


def _small_config(**overrides: Any) -> TimeSeriesTrainingConfig:
    """Build a config that finishes in a few seconds on CPU."""
    base = dict(window_size=50, batch_size=16, epochs=2, early_stopping_patience=2)
    base.update(overrides)
    return TimeSeriesTrainingConfig(**base)


def _timing_config(uri: str) -> TimeSeriesModelConfig:
    return TimeSeriesModelConfig(auxiliary_uris={"timespans": uri})


class TestLnnForwardTimespans:
    """Prove ``timespans`` is actually consumed."""

    def test_forward_consumes_exact_timespans(self) -> None:
        import torch
        torch.manual_seed(0)
        model = LNNClassifier(input_size=5, hidden_size=8, n_layers=1, num_classes=2)
        model.eval()
        x = torch.randn(3, 10, 5)
        regular = torch.ones(3, 10)
        irregular = torch.tensor(
            [[0.1, 5.0, 0.2, 5.0, 0.1, 5.0, 0.2, 5.0, 0.1, 5.0]] * 3,
        )
        with torch.no_grad():
            assert not torch.allclose(model(x, regular), model(x, irregular))

    @pytest.mark.parametrize("timespans", [None, "zero", "nan"])
    def test_forward_rejects_missing_or_invalid_timespans(self, timespans) -> None:
        import torch
        model = LNNClassifier(input_size=5, hidden_size=8, n_layers=1, num_classes=2)
        x = torch.randn(2, 6, 5)
        value = timespans
        if timespans == "zero":
            value = torch.zeros(2, 6)
        elif timespans == "nan":
            value = torch.full((2, 6), float("nan"))
        with pytest.raises((TypeError, ValueError)):
            model(x, value)


class TestLnnTrainWithTimespans:
    """End-to-end ``train()`` via ``config.extra["timespans_uri"]``."""

    @pytest.fixture
    def timespans_data(
        self, tmp_path: Path, sequence_data: tuple[str, str],
    ) -> tuple[str, str, str]:
        X_uri, y_uri = sequence_data
        rng = np.random.default_rng(7)
        # (100, 50) irregular elapsed-time array, same shape convention
        # as can_window.py's emit_timespans output (positive floats).
        timespans = rng.uniform(low=1.0, high=50.0, size=(100, 50)).astype(np.float32)
        ts_path = tmp_path / "timespans.npy"
        np.save(ts_path, timespans)
        return X_uri, y_uri, str(ts_path)

    def test_train_with_timespans_uri_completes_with_real_metrics(
        self, adapter: LnnTimeSeriesAdapter, timespans_data: tuple[str, str, str],
    ) -> None:
        X_uri, y_uri, timespans_uri = timespans_data
        cfg = _small_config()
        job = adapter.train(
            TimeSeriesModelType.lnn, X_uri=X_uri, y_uri=y_uri, config=cfg,
            model_config=_timing_config(timespans_uri),
        )
        assert job.status == "completed"
        assert {"accuracy", "precision", "recall", "f1"} <= set(job.metrics)
        # Metrics must be real floats derived from the val split, not
        # fabricated placeholders.
        assert isinstance(job.metrics["accuracy"], float)
        assert 0.0 <= job.metrics["accuracy"] <= 1.0
        assert job.model_path and Path(job.model_path).exists()
        payload = __import__("torch").load(job.model_path, weights_only=True)
        assert payload["model_class"] == "ncps.torch.LTC"
        assert payload["timing_digest"] and payload["timing_scale"] > 0

    def test_train_without_timespans_fails_closed(
        self, adapter: LnnTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        X_uri, y_uri = sequence_data
        with pytest.raises(ValueError, match="timespans URI"):
            adapter.train(
                TimeSeriesModelType.lnn, X_uri=X_uri, y_uri=y_uri,
                config=_small_config(),
            )

    def test_predict_after_timespans_training_returns_file_uri(
        self, adapter: LnnTimeSeriesAdapter, timespans_data: tuple[str, str, str],
    ) -> None:
        X_uri, y_uri, timespans_uri = timespans_data
        cfg = _small_config()
        job = adapter.train(
            TimeSeriesModelType.lnn, X_uri=X_uri, y_uri=y_uri, config=cfg,
            model_config=_timing_config(timespans_uri),
        )
        pred_uri = adapter.predict(job.id, X_uri)
        assert pred_uri.startswith("file://")
        payload = np.load(pred_uri.removeprefix("file://"))
        assert payload["y_pred"].shape == (100,) or payload["y_pred"].shape[0] > 0
        assert payload["y_score"].shape == payload["y_pred"].shape
