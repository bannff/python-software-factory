"""Non-native sklearn transfer baselines."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def train_sklearn_transfer(
    kind: str, X, y, X_val, y_val, iteration: int,
    save: Callable[[str, Any, dict, int], str],
):
    """Fit and persist one scratch sklearn baseline."""
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    if kind == "random_forest":
        model = RandomForestClassifier(
            n_estimators=100, random_state=42, n_jobs=-1,
        )
    elif kind == "grad_boost":
        model = GradientBoostingClassifier(n_estimators=100, random_state=42)
    else:
        raise ValueError(f"Unknown model type: {kind}")
    model.fit(X, y)
    scores, predicted = model.predict_proba(X_val)[:, 1], model.predict(X_val)
    metrics = {
        "auroc": float(roc_auc_score(y_val, scores)),
        "accuracy": float(accuracy_score(y_val, predicted)),
        "f1": float(f1_score(y_val, predicted)), "transfer_from": "scratch",
    }
    save(kind, model, metrics, iteration)
    return model, metrics


__all__ = ["train_sklearn_transfer"]
