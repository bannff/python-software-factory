"""Pure-Python computational evaluators for CAN failure prediction.

These evaluators operate on pre-computed arrays (y_true, y_pred, scores)
without invoking an LLM. They live at a different evaluation level
(COMPUTATIONAL) than the Strands evaluators (OUTPUT/TRACE/SESSION).

Used by the evals_evaluate_computational MCP tool.
"""

from __future__ import annotations

from typing import Any, Callable

from sklearn.metrics import average_precision_score

from .can_synthetic_evaluators import (
    can_distribution_similarity,
    can_mode_coverage,
    can_statistical_fidelity,
    can_temporal_coherence,
)


def _coerce(
    y_true: list, y_pred: list, scores: list
) -> tuple[list[int], list[int], list[float]]:
    """Coerce and length-check all three input arrays."""
    y_t = [int(x) for x in y_true]
    y_p = [int(x) for x in y_pred]
    s = [float(x) for x in scores]
    if not (len(y_t) == len(y_p) == len(s)):
        raise ValueError("y_true, y_pred, scores must have equal length")
    return y_t, y_p, s


def can_auroc(y_true: list, y_pred: list, scores: list) -> dict[str, Any]:
    """Area under the ROC curve via the Mann-Whitney U statistic."""
    y_t, _, s = _coerce(y_true, y_pred, scores)
    pos = [v for v, t in zip(s, y_t) if t == 1]
    neg = [v for v, t in zip(s, y_t) if t == 0]
    if not pos or not neg:
        return {"evaluator": "can_auroc", "score": 0.0}
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return {"evaluator": "can_auroc", "score": wins / (len(pos) * len(neg))}


def can_auprc(y_true: list, y_pred: list, scores: list) -> dict[str, Any]:
    """Average precision for binary CAN failure labels."""
    if any(label not in (0, 1) for label in y_true):
        raise ValueError("y_true labels must be binary values in {0, 1}")
    y_t, _, s = _coerce(y_true, y_pred, scores)
    if not y_t or not any(y_t):
        return {"evaluator": "can_auprc", "score": 0.0}
    score = float(average_precision_score(y_t, s))
    return {"evaluator": "can_auprc", "score": score}


def can_brier(y_true: list, y_pred: list, scores: list) -> dict[str, Any]:
    """Brier score — mean squared error of probabilities. Lower is better."""
    y_t, _, s = _coerce(y_true, y_pred, scores)
    if not y_t:
        return {"evaluator": "can_brier", "score": 0.0}
    clipped = [max(0.0, min(1.0, v)) for v in s]
    mse = sum((p - t) ** 2 for p, t in zip(clipped, y_t)) / len(y_t)
    return {"evaluator": "can_brier", "score": round(mse, 6)}


def can_lead_time(y_true: list, y_pred: list, scores: list) -> dict[str, Any]:
    """Mean lead time in samples from earliest detection to failure onset."""
    y_t, y_p, _ = _coerce(y_true, y_pred, scores)
    onset = next((i for i, t in enumerate(y_t) if t == 1), None)
    if onset is None or onset == 0:
        return {"evaluator": "can_lead_time", "score": 0.0}
    lead_indices = [i for i, p in enumerate(y_p) if p == 1 and i < onset]
    if not lead_indices:
        return {"evaluator": "can_lead_time", "score": 0.0}
    earliest = min(lead_indices)
    return {"evaluator": "can_lead_time", "score": float(onset - earliest)}


def can_false_alarm(y_true: list, y_pred: list, scores: list) -> dict[str, Any]:
    """False alarm rate: FP / (FP + TN)."""
    y_t, y_p, _ = _coerce(y_true, y_pred, scores)
    fp = sum(1 for t, p in zip(y_t, y_p) if t == 0 and p == 1)
    tn = sum(1 for t, p in zip(y_t, y_p) if t == 0 and p == 0)
    if (fp + tn) == 0:
        return {"evaluator": "can_false_alarm", "score": 0.0}
    return {"evaluator": "can_false_alarm", "score": round(fp / (fp + tn), 6)}


def can_episode_recall(
    y_true: list, y_pred: list, scores: list
) -> dict[str, Any]:
    """Episode-level recall — fraction of contiguous positive runs detected."""
    y_t, y_p, _ = _coerce(y_true, y_pred, scores)
    episodes: list[tuple[int, int]] = []
    start: int | None = None
    for i, t in enumerate(y_t):
        if t == 1 and start is None:
            start = i
        elif t == 0 and start is not None:
            episodes.append((start, i))
            start = None
    if start is not None:
        episodes.append((start, len(y_t)))
    if not episodes:
        return {"evaluator": "can_episode_recall", "score": 0.0}
    detected = sum(
        1 for s, e in episodes if any(p == 1 for p in y_p[s:e])
    )
    return {"evaluator": "can_episode_recall", "score": detected / len(episodes)}


COMPUTATIONAL_EVALUATORS: dict[str, Callable[..., dict[str, Any]]] = {
    "can_auroc": can_auroc,
    "can_auprc": can_auprc,
    "can_brier": can_brier,
    "can_lead_time": can_lead_time,
    "can_false_alarm": can_false_alarm,
    "can_episode_recall": can_episode_recall,
    "can_distribution_similarity": can_distribution_similarity,
    "can_temporal_coherence": can_temporal_coherence,
    "can_statistical_fidelity": can_statistical_fidelity,
    "can_mode_coverage": can_mode_coverage,
}


def run_computational(
    evaluator_name: str,
    y_true: list,
    y_pred: list,
    scores: list,
) -> dict[str, Any]:
    """Dispatch to a computational evaluator by registered name."""
    fn = COMPUTATIONAL_EVALUATORS.get(evaluator_name)
    if fn is None:
        return {"error": f"Unknown computational evaluator: {evaluator_name}"}
    return fn(y_true, y_pred, scores)
