"""Evals-owned held-out metric computation for CAN model artifacts."""
from __future__ import annotations

import hashlib
import math
from typing import Any, Callable

import numpy as np

from .adapters.temporal_split import (
    temporal_split_strategy, temporal_split_with_shuffle_fallback,
)

from .can_evaluation_contracts import CanEvaluatorProvenance
from .passport_validation import canonical_json

CanEvaluator = Callable[..., dict[str, Any]]
EVALUATOR_TOOL = "evals_evaluate_can_model_evidence"
EVALUATOR_TOOL_IDENTITY = "evals.evaluate-can-model-evidence@v1"
_ENVELOPE_KEYS = {
    "schema", "version", "evaluator_identity", "input_digest", "metrics",
}


def evaluate_holdout(
    X: np.ndarray, y: np.ndarray, model: Any, config: Any,
    evaluator: CanEvaluator,
) -> tuple[dict[str, float], dict[str, Any], CanEvaluatorProvenance]:
    """Invoke Evals over the exact validation split and report split evidence."""
    if not np.isin(y, (0, 1)).all():
        raise ValueError("CAN lifecycle training requires binary labels")
    _, _, X_val, y_val = temporal_split_with_shuffle_fallback(
        X, y, config.validation_split, config.seed,
    )
    probabilities = model.predict_proba(X_val)
    predicted = np.argmax(probabilities, axis=1)
    scored = probabilities[:, 1]
    y_true = y_val.tolist()
    y_pred = predicted.tolist()
    y_score = scored.tolist()
    response = evaluator(y_true=y_true, y_pred=y_pred, y_score=y_score)
    metrics, provenance = _envelope(response, y_true, y_pred, y_score)
    evidence = {
        "scope": "synthetic_sensitivity",
        "split_kind": temporal_split_strategy(y, config.validation_split, config.seed),
        "validation_count": int(len(y_val)),
        "positive_count": int(np.count_nonzero(y_val == 1)),
        "negative_count": int(np.count_nonzero(y_val == 0)),
    }
    return metrics, evidence, provenance


def evaluate_predictions(
    y_true: list[float], y_pred: list[float], y_score: list[float],
    evaluator: CanEvaluator,
) -> tuple[dict[str, float], dict[str, Any], CanEvaluatorProvenance]:
    """Evaluate adapter-produced validation outputs through Evals authority."""
    if not y_true or not (len(y_true) == len(y_pred) == len(y_score)):
        raise ValueError("native validation outputs are empty or misaligned")
    truth = np.asarray(y_true)
    if not np.isin(truth, (0, 1)).all():
        raise ValueError("CAN lifecycle training requires binary labels")
    response = evaluator(y_true=y_true, y_pred=y_pred, y_score=y_score)
    metrics, provenance = _envelope(response, y_true, y_pred, y_score)
    positive = int(np.count_nonzero(truth == 1))
    evidence = {
        "scope": "synthetic_sensitivity", "split_kind": "ordered_holdout",
        "validation_count": len(y_true), "positive_count": positive,
        "negative_count": len(y_true) - positive,
    }
    return metrics, evidence, provenance


def canonical_input_digest(y_true: list, y_pred: list, y_score: list | None) -> str:
    payload = {"y_true": y_true, "y_pred": y_pred, "y_score": y_score}
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _envelope(value, y_true, y_pred, y_score):
    data = _tool_data(value)
    if not isinstance(data, dict) or set(data) != _ENVELOPE_KEYS:
        raise ValueError("Evals CAN evaluator returned malformed evidence envelope")
    try:
        provenance = CanEvaluatorProvenance.model_validate({
            key: data[key] for key in (
                "schema", "version", "evaluator_identity", "input_digest",
            )
        }, strict=True)
    except Exception as exc:
        raise ValueError("Evals CAN evaluator returned unknown provenance") from exc
    expected = canonical_input_digest(y_true, y_pred, y_score)
    if provenance.input_digest != expected:
        raise ValueError("Evals CAN evaluator input digest mismatch")
    return _metrics(data["metrics"]), provenance


def _tool_data(value: Any) -> Any:
    """Require successful ToolResult egress and unwrap its typed payload."""
    if hasattr(value, "ok"):
        if not value.ok or value.data is None:
            raise ValueError(f"Evals CAN evaluator failed: {value.error}")
        return value.data.model_dump() if hasattr(value.data, "model_dump") else value.data
    if isinstance(value, dict) and value.get("schema_version") == "v1":
        if value.get("ok") is not True or value.get("data") is None:
            raise ValueError(f"Evals CAN evaluator failed: {value.get('error')}")
        return value["data"]
    return value


def _metrics(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or not value:
        raise ValueError("Evals CAN evaluator returned malformed metrics")
    metrics = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            raise ValueError("Evals CAN evaluator returned malformed metrics")
        # Evals' typed DTO uses null for score-gated metrics unavailable on a
        # one-class validation split; preserve the prior absent-metric meaning.
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError("Evals CAN evaluator returned malformed metrics")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError("Evals CAN evaluator returned nonfinite metrics")
        metrics[key] = number
    return metrics


__all__ = [
    "CanEvaluator", "EVALUATOR_TOOL", "EVALUATOR_TOOL_IDENTITY",
    "canonical_input_digest", "evaluate_holdout", "evaluate_predictions",
]
