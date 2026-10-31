"""CAN model evaluation wrapper.

Thin wrapper that runs the computational evaluators from Epic 0 against
trained model predictions. Used by the CAN failure eval harness to score
CAN failure-prediction models uniformly — accuracy/precision/recall/f1
are always reported; AUROC/AUPRC/Brier require probability scores.
Lead time, false-alarm rate, and episode recall extend the score-based
suite with operational metrics sourced from the same registry.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
)

from .computational_evaluators import run_computational

CAN_EVIDENCE_SCHEMA = "evals.can-model-evidence"
CAN_EVIDENCE_VERSION = "1.0"
CAN_EVALUATOR_IDENTITY = "evals.can-model@v1"


def canonical_input_digest(
    y_true: list | np.ndarray,
    y_pred: list | np.ndarray,
    y_score: list | np.ndarray | None,
) -> str:
    """Hash the exact canonical JSON arrays supplied to the evaluator."""
    payload = {
        "y_true": _json_array(y_true),
        "y_pred": _json_array(y_pred),
        "y_score": None if y_score is None else _json_array(y_score),
    }
    encoded = json.dumps(
        payload, allow_nan=False, separators=(",", ":"), sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _json_array(value: list | np.ndarray) -> list[Any]:
    raw = value.tolist() if isinstance(value, np.ndarray) else value
    if not isinstance(raw, list):
        raise ValueError("CAN evaluator inputs must be arrays")
    return json.loads(json.dumps(raw, allow_nan=False))


def evaluate_can_model(
    y_true: list | np.ndarray,
    y_pred: list | np.ndarray,
    y_score: list | np.ndarray | None = None,
) -> dict[str, float]:
    """Run CAN-specific metrics on (y_true, y_pred) and optional y_score.

    Returns accuracy/precision/recall/f1 always. When y_score is provided
    and y_true has both classes, also returns the full production suite:
    auroc, auprc, brier (score-based) and lead_time, false_alarm,
    episode_recall (binary-prediction-based). All six computational
    evaluators are sourced from :mod:`computational_evaluators` so the
    scoring pipeline stays single-source-of-truth.
    """
    yt = np.asarray(y_true).ravel().astype(int)
    yp = np.asarray(y_pred).ravel().astype(int)
    if len(yt) != len(yp):
        raise ValueError("y_true and y_pred must have equal length")
    ys_array = None if y_score is None else np.asarray(y_score, dtype=float).ravel()
    if ys_array is not None and len(ys_array) != len(yt):
        raise ValueError("y_true, y_pred, and y_score must have equal length")
    if len(yt) == 0:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    results: dict[str, float] = {
        "accuracy": float(accuracy_score(yt, yp)),
        "precision": float(precision_score(yt, yp, zero_division=0)),
        "recall": float(recall_score(yt, yp, zero_division=0)),
        "f1": float(f1_score(yt, yp, zero_division=0)),
    }
    if ys_array is None or len(np.unique(yt)) < 2:
        return results
    ys = ys_array.tolist()
    yt_list, yp_list = yt.tolist(), yp.tolist()
    # Score-based evaluators (need probabilities) — Epic 0 computational
    # evaluators, dispatched through the registry for one source of truth.
    results["auroc"] = float(run_computational(
        "can_auroc", y_true=yt_list, y_pred=yp_list, scores=ys,
    )["score"])
    results["auprc"] = float(run_computational(
        "can_auprc", y_true=yt_list, y_pred=yp_list, scores=ys,
    )["score"])
    results["brier"] = float(run_computational(
        "can_brier", y_true=yt_list, y_pred=yp_list, scores=ys,
    )["score"])
    # Operational evaluators (need only binary y_pred) — how early do we
    # warn (lead_time), how noisy are we (false_alarm), what fraction of
    # failure episodes do we actually catch (episode_recall).
    results["lead_time"] = float(run_computational(
        "can_lead_time", y_true=yt_list, y_pred=yp_list, scores=ys,
    )["score"])
    results["false_alarm"] = float(run_computational(
        "can_false_alarm", y_true=yt_list, y_pred=yp_list, scores=ys,
    )["score"])
    results["episode_recall"] = float(run_computational(
        "can_episode_recall", y_true=yt_list, y_pred=yp_list, scores=ys,
    )["score"])
    return results


def evaluate_can_model_evidence(
    y_true: list | np.ndarray,
    y_pred: list | np.ndarray,
    y_score: list | np.ndarray | None = None,
) -> dict[str, Any]:
    """Return strict versioned metrics and canonical Evals provenance."""
    return {
        "schema": CAN_EVIDENCE_SCHEMA,
        "version": CAN_EVIDENCE_VERSION,
        "evaluator_identity": CAN_EVALUATOR_IDENTITY,
        "input_digest": canonical_input_digest(y_true, y_pred, y_score),
        "metrics": evaluate_can_model(y_true, y_pred, y_score),
    }
