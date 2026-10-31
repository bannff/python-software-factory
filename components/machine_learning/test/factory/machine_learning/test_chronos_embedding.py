"""Focused Chronos validation-holdout scoring regression."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


torch = pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters import chronos_embedding  # noqa: E402


class _Backbone(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.config = SimpleNamespace(d_model=3)


def test_train_probe_scores_validation_raw_once_and_exports_validation_arrays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    X = np.arange(80, dtype=np.float32).reshape(10, 4, 2)
    y = np.array([0, 1] * 5, dtype=np.int64)
    x_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(x_path, X)
    np.save(y_path, y)
    probabilities = np.array([[0.2, 0.8], [0.7, 0.3]], dtype=np.float32)
    calls: list[tuple[object, ...]] = []

    def score(*args):
        calls.append(args)
        return probabilities

    monkeypatch.setattr(chronos_embedding, "score_chronos_classifier", score)
    _, _, extra = chronos_embedding.train_probe(
        SimpleNamespace(inner_model=_Backbone()), tmp_path / "adapter",
        str(x_path), str(y_path), window_size=4, epochs=0, batch_size=2,
        learning_rate=1e-3, validation_split=0.2, seed=42,
        early_stopping_patience=1, lora=False, lora_config=None,
    )

    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0][2], X[-2:])
    assert extra["val_y_true"] == [0.0, 1.0]
    assert extra["val_y_pred"] == [1.0, 0.0]
    np.testing.assert_allclose(extra["val_y_score"], [0.8, 0.3])
