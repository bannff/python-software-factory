"""Correlation-matrix primitives for failure injection (Phase 5).

Extracted from :mod:`_correlation_injection_helpers` to keep that
orchestrator under the 200-LOC factory ceiling. The functions here
are pure data-shaping primitives:

* :func:`normalize_correlation_matrix` — accept any of the documented
  matrix shapes and return a uniform ``dict[(a, b), r]``.
* :func:`build_envelope` — produce the 0 -> 1 -> 1 -> 0 ramp that
  gives correlation injection its gradual onset/decay.
* :func:`pick_root_cluster` — sample a root signal and its coupled
  neighbors, weighted by coupling degree.

The orchestrator (which mutates records) lives in
:mod:`_correlation_injection_helpers`. Nothing here is part of the
public brick surface.
"""

from __future__ import annotations

from typing import Any

import numpy as np


# Minimum |r| for a pair to be considered "correlated enough" to
# corrupt together. Below this threshold we treat the signals as
# independent and the orchestrator falls back to a single-signal
# pick.
DEFAULT_CORRELATION_THRESHOLD: float = 0.7


def normalize_correlation_matrix(
    correlation_matrix: Any,
    signal_names: list[str],
) -> dict[tuple[str, str], float]:
    """Normalize any supported matrix shape to a pair-keyed dict.

    Supported shapes:

    * 2D array-like (F x F) aligned to the CAN ID's signal order.
    * list of ``(a, b, r)`` triples (the ``can_profile`` schema).
    * dict keyed by ``(a, b)`` (tuple or list keys) with float ``r``.
    * ``None`` or any unrecognized shape → empty dict.

    Empty output means "no known correlations" — the orchestrator
    degrades gracefully by picking a single random signal.
    """
    if correlation_matrix is None:
        return {}
    if hasattr(correlation_matrix, "shape") and not isinstance(
        correlation_matrix, (dict, str, bytes),
    ):
        arr = np.asarray(correlation_matrix, dtype=float)
        if arr.ndim == 2 and arr.shape == (len(signal_names), len(signal_names)):
            out: dict[tuple[str, str], float] = {}
            for i, a in enumerate(signal_names):
                for j in range(i + 1, len(signal_names)):
                    b = signal_names[j]
                    r = float(arr[i, j])
                    if r != 0.0:
                        out[(a, b)] = r
            return out
    if isinstance(correlation_matrix, (list, tuple)) and correlation_matrix:
        if all(
            isinstance(t, (list, tuple)) and len(t) == 3
            for t in correlation_matrix
        ):
            return {(t[0], t[1]): float(t[2]) for t in correlation_matrix}
    if isinstance(correlation_matrix, dict):
        out: dict[tuple[str, str], float] = {}
        for k, v in correlation_matrix.items():
            if isinstance(k, (list, tuple)) and len(k) == 2:
                out[(k[0], k[1])] = float(v)
        return out
    return {}


def build_envelope(
    n_frames: int,
    onset_frames: int = 10,
    decay_frames: int = 10,
    mode: str = "linear",
) -> np.ndarray:
    """Return a ``(n_frames,)`` envelope ramping 0 -> 1 -> 1 -> 0.

    ``mode``:

    * ``"linear"``  — straight line segments on each ramp.
    * ``"sigmoid"`` — smooth S-curve on each ramp.

    Degenerate inputs are handled so the envelope always starts and
    ends at 0:

    * ``n_frames <= 0`` — empty array.
    * ``onset + decay > n_frames`` — split the window evenly between
      onset and decay (no sustained plateau); the peak sits in the
      middle so the synthetic failure still has a clean ramp-down.
    """
    if n_frames <= 0:
        return np.zeros(0, dtype=float)
    onset = max(0, int(onset_frames))
    decay = max(0, int(decay_frames))
    if onset + decay > n_frames:
        # Symmetric split: each ramp gets half the window, no plateau.
        onset = n_frames // 2
        decay = n_frames - onset
    sustained = n_frames - onset - decay

    out = np.zeros(n_frames, dtype=float)
    if onset > 0:
        if mode == "sigmoid":
            x = np.linspace(-6.0, 6.0, onset)
            out[:onset] = 1.0 / (1.0 + np.exp(-x))
        else:
            out[:onset] = np.linspace(0.0, 1.0, onset)
    if sustained > 0:
        out[onset:onset + sustained] = 1.0
    if decay > 0:
        if mode == "sigmoid":
            x = np.linspace(6.0, -6.0, decay)
            out[onset + sustained:] = 1.0 / (1.0 + np.exp(-x))
        else:
            out[onset + sustained:] = np.linspace(1.0, 0.0, decay)
    return out


def pick_root_cluster(
    pair_corr: dict[tuple[str, str], float],
    signal_names: list[str],
    rng: np.random.Generator,
    min_corr: float = DEFAULT_CORRELATION_THRESHOLD,
) -> list[str]:
    """Pick a root signal and its correlated neighbors.

    Roots are sampled with probability proportional to node degree
    so highly-coupled signals (which propagate failure more widely
    in real buses) are picked more often. Returns
    ``[root, neighbor_1, neighbor_2, ...]``.

    Falls back to a single uniform-random signal when no strong
    pairs exist so the strategy always emits a failure event.
    """
    if not signal_names:
        return []
    edges: dict[str, list[str]] = {n: [] for n in signal_names}
    for (a, b), r in pair_corr.items():
        if abs(r) >= min_corr and a in edges and b in edges:
            edges[a].append(b)
            edges[b].append(a)
    candidates = [n for n in signal_names if edges[n]]
    if not candidates:
        return [str(rng.choice(signal_names))]
    weights = np.array([max(len(edges[n]), 1) for n in candidates], dtype=float)
    weights /= weights.sum()
    root = str(rng.choice(candidates, p=weights))
    return [root, *edges[root]]


__all__ = [
    "DEFAULT_CORRELATION_THRESHOLD",
    "build_envelope",
    "normalize_correlation_matrix",
    "pick_root_cluster",
]
