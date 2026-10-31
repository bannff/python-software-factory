"""Hybrid (rule + learned) failure injection helpers.

Extracted from :mod:`failure_injection` to keep that orchestrator under
the 200-LOC factory ceiling. The hybrid strategy blends the existing
eight rule-based fault modes with a learned failure generator
(typically a conditional TimeGAN trained on SCANIA APS patterns).

Three sub-strategies are supported:

* ``"rule"``    — 100% rule-based (the legacy behavior).
* ``"learned"`` — 100% learned via the ``LearnedSampler`` callable.
* ``"hybrid"``  — 30% rule / 70% learned, picked per event.

Blending math: the learned window is a z-score-normalized
``(T, F)`` trajectory. We anchor the trajectory's first frame to the
records' pre-failure baseline (the actual decoded signal values) and
linearly interpolate to the learned failure endpoint, so the transition
into the failure is smooth and physically plausible.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


# Per-event split: ~30% rule-based, ~70% learned. The choice is a uniform
# draw per event so the realized fraction tracks the configured weights
# over a large enough sample (>=20 events).
HYBRID_RULE_FRACTION: float = 0.30

# Failure-mode vocabulary for the learned (TimeGAN) channel. The three
# modes are the SCANIA label builder's defaults — keeping them in one
# place means ``failure_mode`` strings stay stable across train/sample.
LEARNED_FAILURE_MODES: tuple[str, ...] = (
    "aps_failure",
    "amplitude_spike",
    "signal_drift",
)

VALID_STRATEGIES: frozenset[str] = frozenset(
    {"rule", "learned", "hybrid", "correlation"},
)

# A learned sampler returns a z-score normalized ``(T, F)`` window.
LearnedSampler = Callable[[int, str, int, np.random.Generator], np.ndarray]


def pick_event_strategy(rng: np.random.Generator) -> str:
    """Return ``"rule"`` or ``"learned"`` per the hybrid 30/70 split."""
    return "rule" if rng.random() < HYBRID_RULE_FRACTION else "learned"


def pick_learned_mode(idx: int, rng: np.random.Generator) -> str:
    """Pick a learned failure mode cycling through the SCANIA vocabulary."""
    return LEARNED_FAILURE_MODES[idx % len(LEARNED_FAILURE_MODES)]


def validate_strategy(
    injection_strategy: str,
    learned_sampler: LearnedSampler | None,
) -> None:
    """Reject invalid strategies and missing samplers for the learned path."""
    if injection_strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"Unknown injection_strategy={injection_strategy!r}; "
            f"expected one of {sorted(VALID_STRATEGIES)}",
        )
    if injection_strategy in ("learned", "hybrid") and learned_sampler is None:
        raise ValueError(
            f"injection_strategy={injection_strategy!r} requires a "
            f"`learned_sampler` callable; got None",
        )


def _collect_baseline_signals(
    records: list[dict[str, Any]],
    start: int,
    end: int,
) -> tuple[list[str], np.ndarray]:
    """Return ``(signal_names, baseline)`` for ``records[start:end]``.

    ``baseline`` is the per-frame mean of the decoded signals
    (frame axis 0, signal axis 1); frames with no signals are skipped.
    The first record that exposes a decoded-signals dict anchors the
    column ordering.
    """
    signal_names: list[str] = []
    for r in records[start:end]:
        sigs = r.get("decoded_signals") or {}
        if sigs:
            signal_names = sorted(sigs.keys())
            break
    if not signal_names:
        return [], np.empty((0, 0), dtype=float)

    n_frames = end - start
    baseline = np.zeros((n_frames, len(signal_names)), dtype=float)
    for i, r in enumerate(records[start:end]):
        sigs = r.get("decoded_signals") or {}
        for j, name in enumerate(signal_names):
            if name in sigs:
                baseline[i, j] = float(sigs[name])
    return signal_names, baseline


def blend_with_context(
    learned_window: np.ndarray,
    baseline: np.ndarray,
    signal_names: list[str],
) -> np.ndarray:
    """Linearly blend the learned window with the records' baseline context.

    ``learned_window`` is a ``(T, F)`` trajectory in z-score space; we
    denormalize it using the baseline's per-signal mean and std, then
    interpolate from the original baseline at ``t=0`` to the learned
    failure endpoint at ``t=T-1``.

    The result is a ``(T, F)`` trajectory in original CAN signal
    space, ready to be written back to ``records[start:end]``.
    """
    T, F = learned_window.shape
    if baseline.shape != (T, F):
        # Defensive: shape mismatch degrades to a direct copy. This
        # should not happen when the sampler is called with the right
        # n_signals argument, but it keeps the function total.
        return np.broadcast_to(learned_window, (T, max(F, baseline.shape[1] if baseline.ndim else 1))).copy()[:T, :F]

    base_mean = baseline.mean(axis=0)
    base_std = baseline.std(axis=0)
    eps = 1e-6
    safe_std = np.where(base_std < eps, 1.0, base_std)

    # Denormalize the learned z-scores into the baseline's signal space.
    denorm = learned_window * safe_std + base_mean

    # Linear interpolation: alpha(t) = t / (T-1), t=0 -> baseline,
    # t=T-1 -> learned failure endpoint. This is the "blend pre-failure
    # context with failure onset" contract.
    alpha = np.linspace(0.0, 1.0, num=T, dtype=float)[:, None]
    blended = (1.0 - alpha) * baseline + alpha * denorm
    return blended


def apply_learned_failure(
    records: list[dict[str, Any]],
    start: int,
    end: int,
    failure_mode: str,
    learned_sampler: LearnedSampler,
    rng: np.random.Generator,
) -> str:
    """Mutate ``records[start:end]`` with a learned failure window.

    Returns the ``failure_mode`` string that was applied (so the caller
    can stamp it onto every record in the window).
    """
    if end - start < 2:
        return failure_mode
    signal_names, baseline = _collect_baseline_signals(records, start, end)
    if not signal_names:
        return failure_mode
    n_frames = end - start
    n_signals = len(signal_names)
    learned_window = np.asarray(
        learned_sampler(n_frames, failure_mode, n_signals, rng),
        dtype=float,
    )
    if learned_window.shape != (n_frames, n_signals):
        # The sampler produced a window of unexpected shape. Truncate or
        # pad with zeros to keep the call total. This is a degraded path;
        # well-behaved samplers always return (n_frames, n_signals).
        out = np.zeros((n_frames, n_signals), dtype=float)
        m = min(learned_window.shape[0], n_frames) if learned_window.ndim else 0
        n = min(learned_window.shape[1] if learned_window.ndim > 1 else 0, n_signals)
        if m and n:
            out[:m, :n] = learned_window[:m, :n]
        learned_window = out

    blended = blend_with_context(learned_window, baseline, signal_names)
    for i, rec in enumerate(records[start:end]):
        sigs = rec.get("decoded_signals")
        if not sigs:
            continue
        for j, name in enumerate(signal_names):
            if name in sigs:
                sigs[name] = float(blended[i, j])
    return failure_mode
