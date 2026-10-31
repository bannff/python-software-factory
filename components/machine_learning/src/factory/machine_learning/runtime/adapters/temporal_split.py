"""Validation holdout split with deterministic shuffle fallback.

The primary branch keeps the final ``val_split`` fraction as an ordered
holdout. When that holdout is single-class but the prefix is not, the
fallback deterministically shuffles whole rows before splitting. That
fallback is a sensitivity split for classifier evaluation; it is not
temporal or forecasting evidence.
"""
from __future__ import annotations

import numpy as np


def _split_indices(
    y: np.ndarray, val_split: float, seed: int,
) -> tuple[np.ndarray, np.ndarray, str]:
    n_val = max(1, int(len(y) * val_split))
    n_train = max(1, len(y) - n_val)
    indices = np.arange(len(y))
    train_indices, val_indices = indices[:n_train], indices[n_train:]
    split_kind = "ordered_holdout"
    if (
        len(np.unique(y[val_indices])) < 2
        and len(np.unique(y[train_indices])) > 1
    ):
        rng = np.random.default_rng(seed)
        rng.shuffle(indices)
        train_indices, val_indices = indices[:n_train], indices[n_train:]
        split_kind = "seeded_shuffle_sensitivity"
    return train_indices, val_indices, split_kind


def temporal_split_indices(
    y: np.ndarray, val_split: float, seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return original-row train/validation indices for the shared split."""
    train_indices, val_indices, _ = _split_indices(y, val_split, seed)
    return train_indices, val_indices


def temporal_split_strategy(y: np.ndarray, val_split: float, seed: int) -> str:
    """Report split semantics without changing existing split outputs."""
    return _split_indices(y, val_split, seed)[2]


def temporal_split_with_shuffle_fallback(
    X: np.ndarray, y: np.ndarray, val_split: float, seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Slice ``X``/``y`` using the ordered holdout or shuffled fallback."""
    train_indices, val_indices = temporal_split_indices(y, val_split, seed)
    return X[train_indices], y[train_indices], X[val_indices], y[val_indices]


__all__ = [
    "temporal_split_indices", "temporal_split_strategy",
    "temporal_split_with_shuffle_fallback",
]
