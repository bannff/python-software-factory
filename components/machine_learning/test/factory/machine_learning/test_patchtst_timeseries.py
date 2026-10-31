"""PatchTST (Patch Time-Series Transformer) — unit + integration tests.

Mirrors the pattern of :mod:`test_torch_timeseries` so the
``torch_timeseries`` invariants (training completes, predict returns
a file URI, registry round-trips) are enforced for the PatchTST
adapter too. Synthetic data carries a learnable binary label so
the transformer has something to fit on the small window size.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")
pytest.importorskip("transformers", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters.patchtst_timeseries import (  # noqa: E402
    PatchTSTTimeSeriesAdapter,
)
from factory.machine_learning.runtime.ports import (  # noqa: E402
    TimeSeriesModelType, TimeSeriesTrainingConfig,
)


@pytest.fixture
def adapter(tmp_path: Path) -> PatchTSTTimeSeriesAdapter:
    return PatchTSTTimeSeriesAdapter(model_root=tmp_path / "models")


@pytest.fixture
def sequence_data(tmp_path: Path) -> tuple[str, str]:
    """Build (100, 50, 5) sequences with a learnable binary label."""
    rng = np.random.default_rng(42)
    n_samples, n_timesteps, n_features = 100, 50, 5
    X = rng.normal(size=(n_samples, n_timesteps, n_features)).astype(np.float32)
    # Signal: window-mean of feature 0 above 0 -> label 1.
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


class TestPatchTSTAdapter:
    """End-to-end PatchTST adapter on synthetic sequence data."""

    def test_train_completes_with_metrics(
        self, adapter: PatchTSTTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        X_uri, y_uri = sequence_data
        job = adapter.train(
            TimeSeriesModelType.patchtst, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.patchtst
        assert {"accuracy", "precision", "recall", "f1"} <= set(job.metrics)
        assert job.model_path and Path(job.model_path).exists()

    def test_predict_returns_file_uri(
        self, adapter: PatchTSTTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        X_uri, y_uri = sequence_data
        job = adapter.train(
            TimeSeriesModelType.patchtst, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        pred_uri = adapter.predict(job.id, X_uri)
        assert pred_uri.startswith("file://")
        payload = np.load(pred_uri.removeprefix("file://"))
        assert payload["y_pred"].shape == (100,)
        assert payload["y_score"].shape == (100,)

    def test_list_models_after_training(
        self, adapter: PatchTSTTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        X_uri, y_uri = sequence_data
        adapter.train(
            TimeSeriesModelType.patchtst, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        models = adapter.list_models()
        assert len(models) == 1
        assert models[0]["model_type"] == "patchtst"
        assert "auroc" in models[0]

    def test_predict_unknown_model_raises(self, adapter: PatchTSTTimeSeriesAdapter) -> None:
        with pytest.raises(KeyError):
            adapter.predict("nonexistent-id", "file:///tmp/X.npy")

    def test_unsupported_model_type_raises(
        self, adapter: PatchTSTTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        X_uri, y_uri = sequence_data
        with pytest.raises(NotImplementedError):
            adapter.train(TimeSeriesModelType.lstm, X_uri=X_uri, y_uri=y_uri)

    def test_compare_models_picks_best(
        self, adapter: PatchTSTTimeSeriesAdapter, sequence_data: tuple[str, str],
    ) -> None:
        X_uri, y_uri = sequence_data
        a = adapter.train(
            TimeSeriesModelType.patchtst, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        b = adapter.train(
            TimeSeriesModelType.patchtst, X_uri=X_uri, y_uri=y_uri,
            config=_small_config(),
        )
        result = adapter.compare_models([a.id, b.id], metric="accuracy")
        assert result["count"] == 2
        assert result["models"][0]["accuracy"] >= result["models"][1]["accuracy"]


class TestPatchTSTModelShape:
    """Sanity-check the PatchTST model itself on the CAN-shaped input."""

    def test_patchtst_forward_shape(self) -> None:
        from factory.machine_learning.runtime.adapters.patchtst_models import (
            PatchTSTClassifier,
        )
        import torch
        # The CAN injected dataset is (n, 50, 60). Verify the model
        # produces (batch, num_classes) for that shape.
        model = PatchTSTClassifier(
            n_channels=60, seq_len=50, patch_len=5, d_model=64,
            n_layers=2, num_classes=2,
        )
        x = torch.randn(8, 50, 60)
        out = model(x)
        assert out.shape == (8, 2)

    def test_patchtst_handles_non_divisible_seq_len(self) -> None:
        """The real HF PatchTSTModel pads internally; unlike the old
        hand-rolled model, a non-divisible seq_len is not an error."""
        from factory.machine_learning.runtime.adapters.patchtst_models import (
            PatchTSTClassifier,
        )
        import torch
        model = PatchTSTClassifier(n_channels=10, seq_len=51, patch_len=5, num_classes=2)
        out = model(torch.randn(4, 51, 10))
        assert out.shape == (4, 2)
