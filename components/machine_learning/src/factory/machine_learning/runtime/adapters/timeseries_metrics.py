"""Shared metric helpers for time-series classifiers.

Single source of truth for the classification metric bundle used by both
the sklearn and torch time-series adapters, so the two stay comparable
on the same scoring surface.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss,
    f1_score, precision_score, recall_score, roc_auc_score,
)

__all__ = ["compute_classification_metrics"]


def compute_classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None = None,
) -> dict[str, float]:
    """Return accuracy / precision / recall / f1, plus AUROC when both classes are present."""
    metrics: dict[str, float] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if y_score is not None and len(np.unique(y_true)) > 1:
        try:
            metrics["auroc"] = float(roc_auc_score(y_true, y_score))
        except ValueError:
            metrics["auroc"] = 0.0
        try:
            metrics["auprc"] = float(average_precision_score(y_true, y_score))
        except ValueError:
            metrics["auprc"] = 0.0
        try:
            metrics["brier"] = float(brier_score_loss(y_true, y_score))
        except ValueError:
            metrics["brier"] = 0.0
    return metrics
