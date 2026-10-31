"""Computational evaluators for synthetic CAN data quality.

These evaluators measure how realistic synthetic CAN signals are
(not classifier performance). They use the same dispatch pattern
as the classifier evaluators but accept structured input: windowed
CAN records (each with window_data + signal_names) or flat
per-signal value lists (legacy). All scores are normalized to
[0, 1] where higher = better quality / closer match to real data.
"""

from __future__ import annotations

from typing import Any, Callable

from ._ks import ks_pvalue, ks_statistic
from ._windowing import is_windowed, window_to_per_signal


def _lag1_autocorr(x: list[float]) -> float:
    """Lag-1 autocorrelation of a 1D series. Returns 0 for degenerate input."""
    n = len(x)
    if n < 2:
        return 0.0
    mean = sum(x) / n
    num = sum((x[i] - mean) * (x[i + 1] - mean) for i in range(n - 1))
    den = sum((xi - mean) ** 2 for xi in x)
    if den == 0.0:
        return 0.0
    return num / den


def can_distribution_similarity(
    y_true: list, y_pred: list, scores: list
) -> dict[str, Any]:
    """KS-test based distribution similarity per signal.

    Accepts either:
    - Windowed records: ``[{"window_data": (T, S), "signal_names": [...]}, ...]``.
      Each window is aggregated (mean over time steps) to one value
      per signal, then a per-signal KS test is run.
    - Flat per-signal lists: ``[signal_0_values, signal_1_values, ...]``
      (legacy). Each inner list is treated as one signal.

    Returns the mean two-sample KS p-value across signals
    (higher = more similar distributions).
    """
    if not y_true or not y_pred:
        return {"evaluator": "can_distribution_similarity", "score": 0.0}
    w_t = is_windowed(y_true)
    w_p = is_windowed(y_pred)
    if w_t != w_p:
        return {"evaluator": "can_distribution_similarity", "score": 0.0}
    if w_t:
        real = window_to_per_signal(y_true)
        synth = window_to_per_signal(y_pred)
        common = [n for n in real if n in synth]
        pairs = [(sorted(real[n]), sorted(synth[n])) for n in common]
    else:
        n = min(len(y_true), len(y_pred))
        pairs = [
            (
                sorted(float(v) for v in y_true[i]),
                sorted(float(v) for v in y_pred[i]),
            )
            for i in range(n)
        ]
    p_values: list[float] = []
    for r, s in pairs:
        if not r or not s:
            p_values.append(0.0)
            continue
        p_values.append(ks_pvalue(ks_statistic(r, s), len(r), len(s)))
    if not p_values:
        return {"evaluator": "can_distribution_similarity", "score": 0.0}
    return {
        "evaluator": "can_distribution_similarity",
        "score": sum(p_values) / len(p_values),
    }


def can_temporal_coherence(
    y_true: list, y_pred: list, scores: list
) -> dict[str, Any]:
    """Temporal coherence via lag-1 autocorrelation match.

    Returns 1.0 - mean |autocorr_real - autocorr_synth| across signals.
    Higher = better temporal match.
    """
    if not y_true or not y_pred:
        return {"evaluator": "can_temporal_coherence", "score": 0.0}
    n = min(len(y_true), len(y_pred))
    diffs: list[float] = []
    for i in range(n):
        r = [float(v) for v in y_true[i]]
        s = [float(v) for v in y_pred[i]]
        diffs.append(abs(_lag1_autocorr(r) - _lag1_autocorr(s)))
    if not diffs:
        return {"evaluator": "can_temporal_coherence", "score": 0.0}
    return {
        "evaluator": "can_temporal_coherence",
        "score": max(0.0, min(1.0, 1.0 - sum(diffs) / len(diffs))),
    }


def can_statistical_fidelity(
    y_true: list, y_pred: list, scores: list
) -> dict[str, Any]:
    """Statistical fidelity via normalized mean error.

    Args:
        y_true: real_stats — dict {signal: {min, max, mean}}.
        y_pred: synth_stats — same shape.

    Returns:
        1.0 - mean(|real_mean - synth_mean| / (real_max - real_min)).
    """
    if not y_true or not y_pred:
        return {"evaluator": "can_statistical_fidelity", "score": 0.0}
    keys = [k for k in y_true if k in y_pred]
    if not keys:
        return {"evaluator": "can_statistical_fidelity", "score": 0.0}
    errs: list[float] = []
    for k in keys:
        r = y_true[k]
        s = y_pred[k]
        rng = r["max"] - r["min"]
        if rng > 0:
            errs.append(abs(r["mean"] - s["mean"]) / rng)
    if not errs:
        return {"evaluator": "can_statistical_fidelity", "score": 0.0}
    return {
        "evaluator": "can_statistical_fidelity",
        "score": max(0.0, min(1.0, 1.0 - sum(errs) / len(errs))),
    }


def can_mode_coverage(
    y_true: list, y_pred: list, scores: list
) -> dict[str, Any]:
    """Mode coverage: fraction of signals whose real range is covered by synthetic.

    For each signal, returns 1.0 if synth_min <= real_min AND
    synth_max >= real_max, else 0.0. Score is the fraction of
    signals satisfying this. 1.0 = perfect coverage, 0.0 = none.
    """
    if not y_true or not y_pred:
        return {"evaluator": "can_mode_coverage", "score": 0.0}
    n = min(len(y_true), len(y_pred))
    covered = 0
    for i in range(n):
        r = [float(v) for v in y_true[i]]
        s = [float(v) for v in y_pred[i]]
        if not r or not s:
            continue
        if min(s) <= min(r) and max(s) >= max(r):
            covered += 1
    return {
        "evaluator": "can_mode_coverage",
        "score": covered / n if n else 0.0,
    }


CAN_SYNTHETIC_EVALUATORS: dict[str, Callable[..., dict[str, Any]]] = {
    "can_distribution_similarity": can_distribution_similarity,
    "can_temporal_coherence": can_temporal_coherence,
    "can_statistical_fidelity": can_statistical_fidelity,
    "can_mode_coverage": can_mode_coverage,
}


__all__ = [
    "CAN_SYNTHETIC_EVALUATORS",
    "can_distribution_similarity",
    "can_temporal_coherence",
    "can_statistical_fidelity",
    "can_mode_coverage",
]
