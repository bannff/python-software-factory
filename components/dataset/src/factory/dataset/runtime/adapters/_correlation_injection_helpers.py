"""Correlation-based failure injection orchestrator (Phase 5).

The fourth injection strategy for the CAN failure-prediction pipeline.
Mutates ``records[start:end]`` so a cluster of correlated signals
(maybe 2-4, picked from the precomputed matrix) is corrupted
together with a gradual onset/sustained/decay envelope.

This is physically realistic: real CAN bus faults (EMI bursts,
connector corrosion, ECU power dips) couple signals together, so
a single root cause produces observable symptoms on multiple lines.
A noise burst on the engine RPM line, for instance, also perturbs
the correlated vehicle-speed signal.

Why a separate file: the data-shaping primitives
(:func:`normalize_correlation_matrix`, :func:`build_envelope`,
:func:`pick_root_cluster`) live in :mod:`_correlation_matrix_helpers`
so this orchestrator stays under the 200-LOC factory ceiling.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ._correlation_matrix_helpers import (
    DEFAULT_CORRELATION_THRESHOLD,
    build_envelope,
    normalize_correlation_matrix,
    pick_root_cluster,
)


CORRELATION_STRATEGY: str = "correlation"

# Default noise multiplier — noise std is
# ``envelope * noise_multiplier * local_signal_std`` so this controls
# how loud the synthetic fault is relative to each signal's natural
# variation. 3x matches the existing sensor_degradation rule mode.
DEFAULT_NOISE_MULTIPLIER: float = 3.0


def validate_correlation_strategy(
    injection_strategy: str, correlation_matrix: Any,
) -> None:
    """Reject ``"correlation"`` strategy when no matrix is supplied.

    Without a matrix, the helper degrades to a single-signal pick
    which defeats the point of the strategy, so we fail loudly and
    let the caller pass the matrix from ``can_profile`` (or a JSON
    file via ``correlation_matrix_uri``).
    """
    if injection_strategy == "correlation" and correlation_matrix is None:
        raise ValueError(
            "injection_strategy='correlation' requires a non-None "
            "`correlation_matrix`; pass it via the can_synthesize "
            "config or let it be auto-extracted from the "
            "constraint_schema (can_profile).",
        )


def apply_correlation_failure(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    failure_mode: str,
    correlation_matrix: Any,
    *,
    onset_frames: int = 10,
    decay_frames: int = 10,
    envelope_mode: str = "linear",
    noise_multiplier: float = DEFAULT_NOISE_MULTIPLIER,
    min_corr: float = DEFAULT_CORRELATION_THRESHOLD,
    rng: np.random.Generator | None = None,
) -> str:
    """Mutate ``records[start:end]`` with a gradual, correlation-driven corruption.

    Algorithm:

    1. Discover signal names from the first record that exposes them.
    2. Normalize the matrix (any supported shape) to a pair dict.
    3. Pick a root + correlated cluster, weighted by coupling degree.
    4. Build a 0 -> 1 -> 1 -> 0 envelope.
    5. For each frame, draw a single Gaussian shock; apply it to the
       root at full magnitude and to each neighbor scaled by
       ``|corr(root, neighbor)|`` with the correlation's sign so
       positively-coupled signals move together (and anti-coupled
       signals move in the opposite direction). Magnitude is
       ``envelope * noise_multiplier * local_signal_std`` so the
       corruption respects each signal's natural scale.

    Returns the ``failure_mode`` string for the caller to stamp.
    """
    if rng is None:
        rng = np.random.default_rng()
    n_frames = end - start
    if n_frames < 2:
        return failure_mode

    signal_names: list[str] = []
    for r in records[start:end]:
        sigs = r.get("decoded_signals") or {}
        if sigs:
            signal_names = sorted(sigs.keys())
            break
    if not signal_names:
        return failure_mode

    pair_corr = normalize_correlation_matrix(correlation_matrix, signal_names)
    cluster = pick_root_cluster(pair_corr, signal_names, rng, min_corr)
    if not cluster:
        return failure_mode
    root = cluster[0]

    # Correlation-with-root lookup (preserves sign for shock direction).
    corr_with_root: dict[str, float] = {n: 0.0 for n in cluster}
    for n in cluster[1:]:
        if (root, n) in pair_corr:
            corr_with_root[n] = pair_corr[(root, n)]
        elif (n, root) in pair_corr:
            corr_with_root[n] = pair_corr[(n, root)]

    envelope = build_envelope(n_frames, onset_frames, decay_frames, envelope_mode)

    # Per-signal std (fallback to abs(mean) for constant signals).
    series: dict[str, list[float]] = {n: [] for n in cluster}
    for r in records[start:end]:
        sigs = r.get("decoded_signals") or {}
        for n in cluster:
            if n in sigs:
                series[n].append(float(sigs[n]))
    stds: dict[str, float] = {}
    for n, vals in series.items():
        if len(vals) > 1:
            stds[n] = float(np.std(vals))
        elif vals:
            stds[n] = max(abs(float(vals[0])), 1.0)
        else:
            stds[n] = 1.0
        if stds[n] < 1e-9:
            stds[n] = max(abs(float(np.mean(vals))) if vals else 1.0, 1.0)

    for i, rec in enumerate(records[start:end]):
        sigs = rec.get("decoded_signals")
        if not sigs:
            continue
        intensity = float(envelope[i])
        if intensity <= 0.0:
            continue
        # Coherent shock per frame: the SAME disturbance propagates
        # through coupled signals, scaled per-pair by their correlation.
        shock = float(rng.normal(0.0, 1.0))
        for n in cluster:
            if n not in sigs:
                continue
            weight = 1.0 if n == root else abs(corr_with_root[n])
            mag = intensity * noise_multiplier * stds[n] * weight
            if n == root:
                sigs[n] = float(sigs[n]) + shock * mag
            else:
                # Preserve correlation sign: positive coupling -> same
                # direction as the root shock; negative coupling -> invert.
                sign = 1.0 if corr_with_root[n] >= 0.0 else -1.0
                sigs[n] = float(sigs[n]) + sign * shock * mag
    return failure_mode


__all__ = [
    "CORRELATION_STRATEGY",
    "DEFAULT_NOISE_MULTIPLIER",
    "apply_correlation_failure",
    "validate_correlation_strategy",
]
