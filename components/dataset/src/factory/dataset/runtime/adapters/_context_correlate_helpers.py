"""Math helpers for the context correlation stage (factory internal).

Split out of :mod:`context_correlate` to keep the public adapter
under the 200-LOC factory ceiling. Nothing here is part of the
public brick surface; these primitives may change without notice.

Two responsibilities live here:

* :func:`build_context_matrix` / :func:`build_failure_matrix` —
  flatten aligned CAN records into the (N, F) context matrix and
  the (N, M) binary failure-indicator matrix.
* :func:`compute_correlation` + its three backends (Pearson,
  Spearman, binned mutual information) — all in pure numpy so we
  don't pull scipy / sklearn for one stage of the pipeline.
"""
from __future__ import annotations

from typing import Any

import numpy as np

# Bin count for the binned mutual-information estimate. 10 mirrors
# ``sklearn.feature_selection.mutual_info_regression`` and is fine
# for the small per-vehicle windows we typically correlate.
MI_BINS: int = 10


def build_context_matrix(
    record_list: list[dict[str, Any]],
    features: list[str],
    context_field: str,
) -> np.ndarray:
    """Stack per-record context features into an (N, F) float matrix.

    Missing / non-numeric values become NaN so ``np.isfinite`` can
    drop them per correlation pair. Records without a context sub-
    dict (e.g. the non-failure CAN rows that lack enrichment) just
    contribute all-NaN rows, which the pair-level mask discards.
    """
    n = len(record_list)
    out = np.full((n, len(features)), np.nan, dtype=np.float64)
    for i, rec in enumerate(record_list):
        ctx = rec.get(context_field) or {}
        if not isinstance(ctx, dict):
            continue
        for j, feat in enumerate(features):
            v = ctx.get(feat)
            if v is None:
                continue
            try:
                out[i, j] = float(v)
            except (TypeError, ValueError):
                continue
    return out


def build_failure_matrix(
    record_list: list[dict[str, Any]],
    failure_modes: list[str],
    failure_field: str,
) -> np.ndarray:
    """Build a binary (N, M) indicator: 1 if record's mode matches."""
    n = len(record_list)
    out = np.zeros((n, len(failure_modes)), dtype=np.float64)
    for i, rec in enumerate(record_list):
        mode = rec.get(failure_field)
        if mode is None:
            continue
        mode_s = str(mode)
        for j, target in enumerate(failure_modes):
            if mode_s == str(target):
                out[i, j] = 1.0
    return out


def compute_correlation(
    x: np.ndarray, y: np.ndarray, method: str,
) -> float | None:
    """Return the correlation between two equal-length 1-D arrays.

    Returns ``None`` for degenerate inputs (zero variance on either
    side, or empty arrays) so the caller can skip the pair instead
    of emitting a noisy 0.0.
    """
    if x.size < 2 or y.size < 2:
        return None
    if method in ("pearson", "spearman"):
        if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
            return None
        if method == "pearson":
            return float(np.corrcoef(x, y)[0, 1])
        return _spearman(x, y)
    return _mutual_information(x, y)


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Pure-numpy Spearman: average-ranks for ties, then Pearson on ranks."""
    return float(np.corrcoef(_rank(x), _rank(y))[0, 1])


def _rank(x: np.ndarray) -> np.ndarray:
    """Average-ranks for ties — replaces ``scipy.stats.rankdata``.

    The order-preserving ``mergesort`` keeps the rank stable, and
    the ``np.unique`` inverse map averages ranks across ties so
    the Spearman correlation stays on the [-1, 1] scale even with
    repeated values.
    """
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, x.size + 1, dtype=np.float64)
    _, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    if not (counts > 1).any():
        return ranks
    sums = np.zeros_like(ranks)
    np.add.at(sums, inv, ranks)
    counts_f = counts.astype(np.float64)
    return sums[inv] / counts_f[inv]


def _mutual_information(x: np.ndarray, y: np.ndarray) -> float:
    """Binned mutual information in nats, no scipy / sklearn required.

    Standard formula ``I(X;Y) = Σ p(x,y) log(p(x,y) / (p(x) p(y)))``
    applied to ``MI_BINS``-bin 2D histograms. We clamp the minimum
    probability to ``eps`` to avoid ``log(0)`` and return a non-
    negative float. Zero-variance inputs (single bin) naturally
    yield MI=0 so the threshold filter discards them.
    """
    eps = 1e-12
    hist, _, _ = np.histogram2d(x, y, bins=MI_BINS)
    total = hist.sum()
    if total <= 0:
        return 0.0
    p_xy = hist / total
    p_x = p_xy.sum(axis=1, keepdims=True)
    p_y = p_xy.sum(axis=0, keepdims=True)
    denom = p_x @ p_y
    mask = (p_xy > eps) & (denom > eps)
    return float(np.sum(p_xy[mask] * np.log(p_xy[mask] / denom[mask])))


__all__ = [
    "MI_BINS",
    "build_context_matrix",
    "build_failure_matrix",
    "compute_correlation",
]
