"""Regression test for the torch time-series scaler/split ordering bug.

Split out from ``test_torch_timeseries.py`` to keep that file under the
200-LOC budget. Covers: after ``temporal_split_with_shuffle_fallback``
reorders windows (positives clustered early -> shuffle fallback fires),
the ``Xt``/``Xv`` arrays actually fed to the model/eval must be scaled,
not the raw pre-split array.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker  # noqa: E402
from factory.machine_learning.runtime.adapters import torch_timeseries as mod  # noqa: E402
from factory.machine_learning.runtime.adapters.torch_timeseries import (  # noqa: E402
    TorchTimeSeriesAdapter,
)
from factory.machine_learning.runtime.ports import (  # noqa: E402
    TimeSeriesModelType, TimeSeriesTrainingConfig,
)


@pytest.fixture
def adapter(tmp_path: Path) -> TorchTimeSeriesAdapter:
    return TorchTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=tmp_path / "models",
    )


def _small_config(**overrides: Any) -> TimeSeriesTrainingConfig:
    base = dict(window_size=20, batch_size=16, epochs=3, early_stopping_patience=2)
    base.update(overrides)
    return TimeSeriesTrainingConfig(**base)


def test_scaling_applied_when_shuffle_fallback_fires(
    adapter: TorchTimeSeriesAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Xt/Xv fed to the model must be scaled even when the shuffle
    fallback reorders windows (positives clustered in the first ~5%)."""
    rng = np.random.default_rng(0)
    n_samples, n_timesteps, n_features = 200, 20, 5
    # Large raw magnitude + offset so "already scaled" is falsifiable.
    X = (rng.normal(size=(n_samples, n_timesteps, n_features)) * 1000 + 5000).astype(
        np.float32,
    )
    y = np.zeros(n_samples, dtype=np.int64)
    y[: max(1, int(n_samples * 0.05))] = 1  # positives clustered in first 5%
    X_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(X_path, X)
    np.save(y_path, y)

    captured: dict[str, np.ndarray] = {}
    real_fit, real_apply = mod.fit_scaler_transform, mod.apply_scaler

    def spy_fit(arr: np.ndarray, n_train: int):
        X_scaled, mean, scale = real_fit(arr, n_train)
        captured["Xt_scaled"] = X_scaled
        return X_scaled, mean, scale

    def spy_apply(arr: np.ndarray, mean, scale):
        captured["Xv_scaled"] = real_apply(arr, mean, scale)
        return captured["Xv_scaled"]

    monkeypatch.setattr(mod, "fit_scaler_transform", spy_fit)
    monkeypatch.setattr(mod, "apply_scaler", spy_apply)

    adapter.train(
        TimeSeriesModelType.lstm, X_uri=str(X_path), y_uri=str(y_path),
        config=_small_config(validation_split=0.2),
    )

    assert "Xt_scaled" in captured and "Xv_scaled" in captured
    for name, arr in captured.items():
        mean_abs, std = float(np.abs(arr.mean())), float(arr.std())
        assert mean_abs < 0.5, f"{name} mean={mean_abs} not near zero — scaling not applied"
        assert 0.5 < std < 2.0, f"{name} std={std} not near unit variance — scaling not applied"
