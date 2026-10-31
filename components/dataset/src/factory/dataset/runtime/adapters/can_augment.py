"""CAN time-series augmentation stage for the CAN failure-prediction pipeline.

Stage 5 of the CAN failure-prediction pipeline (optional). Sits between
``can_window`` and training. Operates on windowed metadata records
and applies well-understood time-series augmentation techniques to
multiply the training corpus.

Techniques:
    * ``jitter``   — Gaussian noise on signal values (clamped to bounds)
    * ``scale``    — random magnitude scaling per window
    * ``warp``     — non-linear time-axis distortion
    * ``permute``  — shuffle sub-segments within a window

Each technique has a configurable multiplicity. Combined effect is
multiplicative: ``jitter(3) × scale(2) = 6x`` from one input window.

Failure records (``is_failure=1``) pass through unchanged by default
to preserve failure signatures.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np


class CanAugmentStageAdapter:
    """Multiply windowed CAN records via time-series augmentation."""

    name = "can_augment"
    stage_version = "factory-can-augment-1"
    allowed_config = frozenset({
        "techniques", "jitter_std", "scale_range", "warp_factor",
        "permute_segments", "seed", "preserve_failures", "input_uri",
    })

    def execute(
        self,
        records: Iterable[Any],
        config: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield augmented window records."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported can_augment configuration: {sorted(unknown)}"
            )

        techniques = list(values.get("techniques") or ["jitter", "scale"])
        jitter_std = float(values.get("jitter_std", 0.05))
        scale_lo, scale_hi = (float(values.get("scale_range", [0.9, 1.1])[0]),
                               float(values.get("scale_range", [0.9, 1.1])[1]))
        warp_factor = float(values.get("warp_factor", 0.1))
        permute_segs = int(values.get("permute_segments", 5))
        seed = int(values.get("seed", 42))
        preserve_failures = bool(values.get("preserve_failures", True))

        record_list = list(records)
        input_uri = values.get("input_uri")
        if not record_list and input_uri:
            from ..helpers import load_records_from_uri
            record_list = load_records_from_uri(input_uri)

        has_timing = any("timespans" in record for record in record_list)
        if has_timing and set(techniques) & {"warp", "permute"}:
            raise ValueError("time-axis augmentation is incompatible with exact timespans")
        rng = np.random.default_rng(seed)

        for rec in record_list:
            yield rec
            if preserve_failures and rec.get("label"):
                continue
            signal = rec.get("signal") or {}
            signal_values = signal.get("values") if isinstance(signal, dict) else None
            source_values = signal_values if signal_values is not None else rec.get("window_data")
            if not source_values:
                continue

            matrix = np.array(source_values, dtype=np.float64)
            label = rec.get("label", 0)

            for tech in techniques:
                variants = _apply_technique(
                    tech, matrix, rng,
                    jitter_std=jitter_std,
                    scale_range=(scale_lo, scale_hi),
                    warp_factor=warp_factor,
                    permute_segments=permute_segs,
                )
                for v_matrix in variants:
                    out = dict(rec)
                    values = v_matrix.tolist()
                    out["window_data"] = values
                    if isinstance(signal, dict):
                        out["signal"] = {**signal, "values": values}
                    out["label"] = label
                    out["capture_source"] = "augmented"
                    orig_trip = rec.get("trip_id", "synth")
                    out["trip_id"] = f"{orig_trip}_aug_{tech}"
                    yield out


def _apply_technique(
    name: str,
    matrix: np.ndarray,
    rng: np.random.Generator,
    *,
    jitter_std: float,
    scale_range: tuple[float, float],
    warp_factor: float,
    permute_segments: int,
) -> list[np.ndarray]:
    """Apply one augmentation technique, return list of variant matrices."""
    if name == "jitter":
        return [_jitter(matrix, rng, jitter_std)]
    elif name == "scale":
        return [_scale(matrix, rng, scale_range)]
    elif name == "warp":
        return [_warp(matrix, rng, warp_factor)]
    elif name == "permute":
        return [_permute(matrix, rng, permute_segments)]
    return []


def _jitter(
    matrix: np.ndarray, rng: np.random.Generator, std: float,
) -> np.ndarray:
    """Add Gaussian noise scaled to std fraction of each feature's range."""
    noise = rng.normal(0, std, matrix.shape)
    feature_ranges = matrix.max(axis=0) - matrix.min(axis=0)
    feature_ranges[feature_ranges == 0] = 1.0
    return matrix + noise * feature_ranges


def _scale(
    matrix: np.ndarray, rng: np.random.Generator,
    scale_range: tuple[float, float],
) -> np.ndarray:
    """Multiply all features by a random factor."""
    factor = rng.uniform(scale_range[0], scale_range[1])
    return matrix * factor


def _warp(
    matrix: np.ndarray, rng: np.random.Generator, factor: float,
) -> np.ndarray:
    """Non-linearly distort the time axis via piecewise linear warping."""
    n_steps = matrix.shape[0]
    if n_steps < 3:
        return matrix.copy()
    n_knots = max(3, n_steps // 10)
    knot_idx = np.linspace(0, n_steps - 1, n_knots, dtype=int)
    warp_amount = rng.uniform(-factor, factor, size=n_knots)
    src = knot_idx.astype(float)
    dst = knot_idx + warp_amount * n_steps
    dst = np.clip(dst, 0, n_steps - 1)
    dst = np.sort(dst)
    out = np.empty_like(matrix)
    for col in range(matrix.shape[1]):
        out[:, col] = np.interp(
            np.arange(n_steps), dst, matrix[knot_idx, col],
        )
    return out


def _permute(
    matrix: np.ndarray, rng: np.random.Generator, n_segments: int,
) -> np.ndarray:
    """Shuffle non-overlapping sub-segments along the time axis."""
    n_steps = matrix.shape[0]
    seg_len = max(1, n_steps // n_segments)
    indices = np.arange(n_steps)
    segments = [
        indices[i:i + seg_len] for i in range(0, n_steps, seg_len)
    ]
    rng.shuffle(segments)
    order = np.concatenate(segments)
    return matrix[order]
