"""Conditional TimeGAN adapter — training, sampling, and registry tests.

Test strategy mirrors :mod:`test_timegan`: tiny synthetic ``(N, T, F)``
window blocks plus a synthetic one-hot label tensor so the G/D
forward pass completes in a few seconds on CPU. The live SCANIA
smoke test is gated behind ``SCANIA_DATA_URI`` (matches the Phase 1
``test_scania_pattern_extractor`` pattern).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker
from factory.machine_learning.runtime.adapters.timegan_conditional import (
    ConditionalTimeGANAdapter,
)
from factory.machine_learning.runtime.adapters.timegan_conditional_models import (
    ConditionalDiscriminator, ConditionalGenerator,
)
from factory.machine_learning.runtime.ports import (
    TimeSeriesTrainingConfig,
)


# ---- Fixtures -------------------------------------------------------------


@pytest.fixture
def adapter(tmp_path: Path) -> ConditionalTimeGANAdapter:
    """Fresh adapter pointed at a temp model root (registry is per-instance)."""
    a = ConditionalTimeGANAdapter(tracker=MemoryTracker())
    a._root = tmp_path / "models"
    a._root.mkdir(parents=True, exist_ok=True)
    return a


@pytest.fixture
def window_data(tmp_path: Path) -> tuple[str, str]:
    """Build a small (N=24, T=12, F=4) window block + matching one-hot labels.

    Three failure modes (8 windows each) so the G/D sees balanced
    conditioning signal during the fast training pass.
    """
    rng = np.random.default_rng(7)
    n_samples, window_size, n_features = 24, 12, 4
    n_modes = 3
    X = rng.normal(size=(n_samples, window_size, n_features)).astype(np.float32)
    # Inject mode-specific signature so the discriminator has a
    # learnable boundary: mode 0 spikes, mode 1 drifts, mode 2 is
    # baseline noise.
    Y = np.zeros((n_samples, n_modes), dtype=np.float32)
    for i in range(n_samples):
        mode = i % n_modes
        Y[i, mode] = 1.0
        if mode == 0:
            X[i] += 4.0  # amplitude spike
        elif mode == 1:
            ramp = np.linspace(0.0, 3.0, window_size, dtype=np.float32)
            X[i] += ramp[:, None]  # signal drift
    X_path = tmp_path / "X_windows.npy"
    Y_path = tmp_path / "Y_labels.npy"
    np.save(X_path, X)
    np.save(Y_path, Y)
    return str(X_path), str(Y_path)


def _fast_config(mode_names: list[str] | None = None, **overrides: Any) -> TimeSeriesTrainingConfig:
    """Tiny config so tests finish in a few seconds on CPU."""
    base: dict[str, Any] = dict(
        window_size=12, batch_size=8, epochs=1, early_stopping_patience=1,
        extra={
            "latent_dim": 8, "hidden_dim": 16, "n_layers": 1,
            "epochs_reconstruction": 1, "epochs_adversarial": 1,
            "mode_names": mode_names or ["amplitude_spike", "signal_drift", "aps_failure"],
        },
    )
    base.update(overrides)
    return TimeSeriesTrainingConfig(**base)


# ---- Model module unit tests ----------------------------------------------


class TestConditionalModels:
    """Validate the conditional G/D forward-pass shape contract."""

    def test_generator_returns_expected_shape(self) -> None:
        """G(z, c) -> (B, T, n_features) with no NaN/Inf."""
        B, T, L, M, H, F = 4, 10, 8, 3, 16, 5
        G = ConditionalGenerator(L, M, H, n_layers=1, n_features=F)
        z = torch.randn(B, T, L)
        c = torch.eye(M)[[0, 1, 2, 0]]  # 4 different mode indices
        out = G(z, c)
        assert out.shape == (B, T, F)
        assert torch.isfinite(out).all()

    def test_generator_changes_output_with_mode(self) -> None:
        """Same latent z + different mode -> different output (proves conditioning)."""
        torch.manual_seed(0)
        G = ConditionalGenerator(latent_dim=8, n_modes=3, hidden_dim=16,
                                 n_layers=1, n_features=4)
        z = torch.randn(2, 6, 8)
        c_a = torch.tensor([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        c_b = torch.tensor([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]])
        out_a = G(z, c_a)
        out_b = G(z, c_b)
        # Different modes should produce different outputs.
        assert not torch.allclose(out_a, out_b, atol=1e-4)

    def test_discriminator_returns_real_probability(self) -> None:
        """D(x, c) -> (B, 1) in (0, 1) — sigmoid output."""
        B, T, F, M, H = 4, 10, 5, 3, 16
        D = ConditionalDiscriminator(F, M, H, n_layers=1)
        x = torch.randn(B, T, F)
        c = torch.eye(M)[[0, 1, 2, 0]]
        out = D(x, c)
        assert out.shape == (B, 1)
        # Sigmoid output is bounded in (0, 1).
        assert (out > 0.0).all() and (out < 1.0).all()

    def test_discriminator_uses_conditioning(self) -> None:
        """D treats different modes as different inputs (gradient flow)."""
        torch.manual_seed(1)
        D = ConditionalDiscriminator(n_features=4, n_modes=3, hidden_dim=16, n_layers=1)
        x = torch.randn(2, 6, 4)
        c_a = torch.tensor([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        c_b = torch.tensor([[0.0, 1.0, 0.0], [0.0, 1.0, 0.0]])
        out_a = D(x, c_a)
        out_b = D(x, c_b)
        assert not torch.allclose(out_a, out_b, atol=1e-4)


# ---- Adapter training + sampling tests ------------------------------------


class TestConditionalTimeGANAdapter:
    """Train on (X, Y), sample conditioned on a named mode."""

    def test_trains_on_conditioned_data(
        self, adapter: ConditionalTimeGANAdapter, window_data: tuple[str, str],
    ) -> None:
        """Training produces a completed job with conditional metadata."""
        X_uri, Y_uri = window_data
        job = adapter.train(
            X_uri=X_uri, y_uri=Y_uri, config=_fast_config(),
            experiment_name="ctimegan-train",
        )
        assert job.status == "completed"
        assert job.model_path and Path(job.model_path).exists()
        # Conditional metrics include mode vocabulary + n_modes.
        assert job.metrics["n_modes"] == 3
        assert "amplitude_spike" in job.metrics["mode_names"]

    def test_sample_conditioned_on_failure_mode(
        self, adapter: ConditionalTimeGANAdapter, window_data: tuple[str, str],
    ) -> None:
        """Sampling with a named mode returns windows of the right shape."""
        X_uri, Y_uri = window_data
        job = adapter.train(
            X_uri=X_uri, y_uri=Y_uri, config=_fast_config(),
        )
        samples_uri = adapter.sample(
            job.id, n_samples=16, failure_mode="amplitude_spike", seed=42,
        )
        assert samples_uri.startswith("file://")
        samples = np.load(samples_uri.removeprefix("file://"))
        # Match the training window shape: (16, 12, 4).
        assert samples.shape == (16, 12, 4)
        assert np.isfinite(samples).all(), "Conditional samples contain NaN/Inf"

    def test_sample_each_mode_produces_different_distribution(
        self, adapter: ConditionalTimeGANAdapter, window_data: tuple[str, str],
    ) -> None:
        """Two different modes (after minimal training) yield different means.

        This is a smoke test, not a strict separation check: the GAN
        is barely trained, but the mode input must influence the
        output enough to shift the per-mode mean.
        """
        X_uri, Y_uri = window_data
        job = adapter.train(
            X_uri=X_uri, y_uri=Y_uri, config=_fast_config(),
        )
        s_spike = np.load(adapter.sample(
            job.id, n_samples=32, failure_mode="amplitude_spike", seed=42,
        ).removeprefix("file://"))
        s_drift = np.load(adapter.sample(
            job.id, n_samples=32, failure_mode="signal_drift", seed=42,
        ).removeprefix("file://"))
        # Means should differ by at least a small amount. The 1-epoch
        # GAN isn't well-trained, but the mode signal has to perturb
        # the output. A loose tolerance keeps the test stable across
        # torch backends.
        assert abs(s_spike.mean() - s_drift.mean()) > 1e-4

    def test_unknown_failure_mode_raises(
        self, adapter: ConditionalTimeGANAdapter, window_data: tuple[str, str],
    ) -> None:
        """Sample rejects a mode not in the trained vocabulary."""
        X_uri, Y_uri = window_data
        job = adapter.train(X_uri=X_uri, y_uri=Y_uri, config=_fast_config())
        with pytest.raises(KeyError, match="Unknown failure_mode"):
            adapter.sample(job.id, n_samples=8, failure_mode="not_a_mode")

    def test_train_rejects_mismatched_shapes(
        self, adapter: ConditionalTimeGANAdapter, tmp_path: Path,
    ) -> None:
        """X and Y must have the same row count."""
        X = np.random.default_rng(0).normal(size=(10, 8, 3)).astype(np.float32)
        Y = np.zeros((12, 2), dtype=np.float32)
        Y[np.arange(12), np.random.default_rng(0).integers(0, 2, 12)] = 1.0
        x_path = tmp_path / "X.npy"
        y_path = tmp_path / "Y.npy"
        np.save(x_path, X); np.save(y_path, Y)
        with pytest.raises(ValueError, match="row mismatch"):
            adapter.train(
                X_uri=str(x_path), y_uri=str(y_path), config=_fast_config(
                    mode_names=["a", "b"],
                ),
            )

    def test_train_rejects_non_onehot_labels(
        self, adapter: ConditionalTimeGANAdapter, tmp_path: Path,
    ) -> None:
        """Y rows must sum to 1.0; unrecognised distributions fail loudly."""
        X = np.random.default_rng(0).normal(size=(6, 8, 3)).astype(np.float32)
        Y = np.full((6, 2), 0.5, dtype=np.float32)  # sums to 1.0 but not one-hot
        x_path = tmp_path / "X.npy"; y_path = tmp_path / "Y.npy"
        np.save(x_path, X); np.save(y_path, Y)
        with pytest.raises(ValueError, match="one-hot"):
            adapter.train(
                X_uri=str(x_path), y_uri=str(y_path),
                config=_fast_config(mode_names=["a", "b"]),
            )

    def test_get_model_returns_mode_names(
        self, adapter: ConditionalTimeGANAdapter, window_data: tuple[str, str],
    ) -> None:
        """The registry record carries the mode vocabulary for sampling."""
        X_uri, Y_uri = window_data
        job = adapter.train(X_uri=X_uri, y_uri=Y_uri, config=_fast_config())
        rec = adapter.get_model(job.id)
        assert rec is not None
        assert rec["model_type"] == "timegan_conditional"
        assert rec["n_modes"] == 3
        assert rec["mode_names"] == ["amplitude_spike", "signal_drift", "aps_failure"]


# ---- Live SCANIA data integration (opt-in via env var) ---------------------


@pytest.mark.skipif(
    not os.environ.get("SCANIA_DATA_URI"),
    reason="Set SCANIA_DATA_URI + SCANIA_LABELS_URI to run the live smoke test",
)
class TestLiveScaniaConditionalSmoke:
    """End-to-end smoke test against the real SCANIA failure windows."""

    def test_train_and_sample_on_real_scania(self, tmp_path: Path) -> None:
        x_uri = os.environ["SCANIA_DATA_URI"]
        y_uri = os.environ["SCANIA_LABELS_URI"]
        a = ConditionalTimeGANAdapter(tracker=MemoryTracker())
        a._root = tmp_path / "models"
        a._root.mkdir(parents=True, exist_ok=True)
        job = a.train(
            X_uri=x_uri, y_uri=y_uri,
            config=TimeSeriesTrainingConfig(
                window_size=50, batch_size=32, epochs=1,
                extra={
                    "latent_dim": 16, "hidden_dim": 32, "n_layers": 1,
                    "epochs_reconstruction": 1, "epochs_adversarial": 1,
                    "mode_names": ["amplitude_spike", "signal_drift", "aps_failure"],
                },
            ),
        )
        assert job.status == "completed"
        assert job.metrics["n_modes"] == 3
        samples_uri = a.sample(
            job.id, n_samples=10, failure_mode="amplitude_spike", seed=42,
        )
        samples = np.load(samples_uri.removeprefix("file://"))
        assert samples.shape == (10, 50, 170)
        assert np.isfinite(samples).all()
