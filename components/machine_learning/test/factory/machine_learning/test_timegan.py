"""TimeGAN adapter — training, sampling, and registry tests.

The fixture uses a tiny (32, 16, 2) window block to keep the
generator/discriminator training pass under a few seconds on CPU.
This matches the production use case (CAN ID 0x442 has 2 signals)
so the test shape and the real-world shape coincide.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker
from factory.machine_learning.runtime.adapters.timegan import TimeGANAdapter
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelType, TimeSeriesTrainingConfig,
)


@pytest.fixture
def adapter(tmp_path: Path) -> TimeGANAdapter:
    a = TimeGANAdapter(tracker=MemoryTracker())
    a._root = tmp_path / "models"
    a._root.mkdir(parents=True, exist_ok=True)
    return a


@pytest.fixture
def window_data(tmp_path: Path) -> str:
    """Build a small (N, T, F) window fixture and persist as .npy."""
    rng = np.random.default_rng(42)
    n_samples, window_size, n_features = 32, 16, 2  # 0x442 has 2 signals
    X = rng.normal(size=(n_samples, window_size, n_features)).astype(np.float32)
    X_path = tmp_path / "X_windows.npy"
    np.save(X_path, X)
    return str(X_path)


def _fast_config(**overrides: Any) -> TimeSeriesTrainingConfig:
    """Tiny config so tests finish in a few seconds on CPU."""
    base = dict(
        window_size=16, batch_size=8, epochs=1, early_stopping_patience=1,
        extra={
            "latent_dim": 8, "hidden_dim": 16, "n_layers": 1,
            "epochs_reconstruction": 1, "epochs_adversarial": 1,
        },
    )
    base.update(overrides)
    return TimeSeriesTrainingConfig(**base)


class TestTimeGANEnum:
    """Verify the TimeGAN enum value is registered for routing."""

    def test_timegan_enum_exists(self) -> None:
        assert hasattr(TimeSeriesModelType, "timegan")
        assert TimeSeriesModelType.timegan.value == "timegan"


class TestTimeGANAdapter:
    """Verify the TimeGAN adapter trains and samples synthetic windows."""

    def test_timegan_trains_on_sample_data(
        self, adapter: TimeGANAdapter, window_data: str,
    ) -> None:
        """TimeGAN training yields a completed job with generator + discriminator."""
        job = adapter.train(
            X_uri=window_data, config=_fast_config(), experiment_name="timegan-test",
        )
        assert job.status == "completed"
        assert job.model_type == TimeSeriesModelType.timegan
        assert job.model_path and Path(job.model_path).exists()
        # Metrics include loss values + distribution comparison.
        assert "g_loss_final" in job.metrics
        assert "d_loss_final" in job.metrics
        assert "synthetic_mean" in job.metrics
        assert "real_mean" in job.metrics

    def test_timegan_generates_windows(
        self, adapter: TimeGANAdapter, window_data: str,
    ) -> None:
        """Sampling returns a .npy file with synthetic windows."""
        job = adapter.train(
            X_uri=window_data, config=_fast_config(), experiment_name="timegan-sample",
        )
        samples_uri = adapter.sample(job.id, n_samples=128, seed=42)
        assert samples_uri.startswith("file://")
        samples = np.load(samples_uri.removeprefix("file://"))
        # Should have produced exactly 128 windows of the right shape.
        assert samples.shape[0] == 128
        assert samples.shape[1] == 16
        assert samples.shape[2] == 2

    def test_timegan_output_shape_matches_config(
        self, adapter: TimeGANAdapter, window_data: str,
    ) -> None:
        """Sample output window size and feature dim match the training data."""
        job = adapter.train(
            X_uri=window_data, config=_fast_config(), experiment_name="timegan-shape",
        )
        samples_uri = adapter.sample(job.id, n_samples=64, seed=7)
        samples = np.load(samples_uri.removeprefix("file://"))
        real_X = np.load(window_data)
        # Same window_size and n_features as the training data.
        assert samples.shape[1:] == real_X.shape[1:]

    def test_sample_produces_npy_file(
        self, adapter: TimeGANAdapter, window_data: str,
    ) -> None:
        """The sample output is a valid .npy file (loadable, finite values)."""
        job = adapter.train(
            X_uri=window_data, config=_fast_config(), experiment_name="timegan-npy",
        )
        samples_uri = adapter.sample(job.id, n_samples=32, seed=42)
        path = Path(samples_uri.removeprefix("file://"))
        assert path.exists()
        assert path.suffix == ".npy"
        samples = np.load(path)
        # No NaN/Inf — a divergence in the LSTM would surface here.
        assert np.isfinite(samples).all(), "Synthetic windows contain NaN/Inf"

    def test_get_model_returns_metadata(
        self, adapter: TimeGANAdapter, window_data: str,
    ) -> None:
        """get_model returns the registered model record (or None)."""
        job = adapter.train(
            X_uri=window_data, config=_fast_config(), experiment_name="timegan-meta",
        )
        record = adapter.get_model(job.id)
        assert record is not None
        assert record["id"] == job.id
        assert record["model_type"] == "timegan"
        assert "metrics" in record
        assert adapter.get_model("missing") is None
