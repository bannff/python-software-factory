"""Internal helpers for the SCANIA pattern extractor.

Kept under the 200 LOC file ceiling by isolating the pure data-shaping
helpers from the public :class:`ScaniaPatternExtractor` class. Nothing
in this module is part of the public brick surface; it may change
without notice.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


SCANIA_HEADER_LINES = 20
SCANIA_NA_SENTINELS = ("na", "NA", "NaN", "")
SCANIA_POS_LABEL = "pos"
SCANIA_NEG_LABEL = "neg"
SCANIA_FAILURE_MODE = "aps_failure"
SCANIA_BASELINE_MODE = "aps_baseline"


def coerce_records(records: Any) -> list[dict[str, Any]]:
    """Coerce records to a list-of-dicts in canonical ``{class, features}`` form."""
    if isinstance(records, pd.DataFrame):
        out: list[dict[str, Any]] = []
        for _, row in records.iterrows():
            out.append({
                "class": str(row["class"]).strip().lower(),
                "features": {col: row[col] for col in records.columns if col != "class"},
            })
        return out
    if isinstance(records, Mapping):
        return [dict(v) for v in records.values()]
    return list(records)


def feature_matrix(records: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
    """Stack per-record feature dicts into a ``(n, d)`` float matrix.

    NaN entries are replaced with the column mean computed on the
    non-NaN values; all-NaN columns collapse to zero.
    """
    if not records:
        raise ValueError("Cannot build a feature matrix from zero records")
    can_ids = sorted({k for r in records for k in r.get("features", {})})
    if not can_ids:
        raise ValueError("No features found in records")
    matrix = np.empty((len(records), len(can_ids)), dtype=np.float64)
    for i, r in enumerate(records):
        feats = r.get("features") or {}
        for j, cid in enumerate(can_ids):
            v = feats.get(cid, np.nan)
            matrix[i, j] = float(v) if v is not None else np.nan
    col_means = np.nanmean(matrix, axis=0)
    col_means = np.where(np.isnan(col_means), 0.0, col_means)
    nan_mask = np.isnan(matrix)
    matrix = np.where(nan_mask, np.broadcast_to(col_means, matrix.shape), matrix)
    return matrix, can_ids


def build_trajectory(
    failure_row: np.ndarray,
    baseline: np.ndarray,
    window_size: int,
) -> np.ndarray:
    """Linearly interpolate a ``(window_size, d)`` trajectory.

    Frame 0 starts at ``baseline`` and frame ``window_size - 1`` lands
    exactly on ``failure_row``. Intermediate frames are evenly spaced.
    """
    if window_size < 2:
        raise ValueError("window_size must be >= 2")
    alphas = np.linspace(0.0, 1.0, num=window_size, dtype=np.float64)[:, None]
    return (1.0 - alphas) * baseline + alphas * failure_row


def zscore_normalize(trajectories: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Per-feature z-score across the leading axes of ``trajectories``."""
    if trajectories.size == 0:
        return trajectories
    flat = trajectories.reshape(-1, trajectories.shape[-1])
    mean = flat.mean(axis=0)
    std = flat.std(axis=0)
    std = np.where(std < eps, 1.0, std)
    return ((trajectories - mean) / std).astype(np.float64)
