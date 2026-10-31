"""Native-only LightGBM operations imported exclusively by the child worker."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

try:
    from .lightgbm_flavor_contract import lightgbm_metadata, validate_lightgbm_flavor
    from .native_lightgbm_contracts import (
        ArtifactPayload, FitPayload, FitResult, InspectResult, ScorePayload, ScoreResult,
    )
    from .native_lightgbm_models import (
        classifier_booster, load_artifact, load_init_model, outputs,
    )
except ImportError:  # Fixed-path worker execution avoids package initializers.
    from lightgbm_flavor_contract import lightgbm_metadata, validate_lightgbm_flavor
    from native_lightgbm_contracts import (
        ArtifactPayload, FitPayload, FitResult, InspectResult, ScorePayload, ScoreResult,
    )
    from native_lightgbm_models import (
        classifier_booster, load_artifact, load_init_model, outputs,
    )


def _array(uri: str) -> np.ndarray:
    path = urlparse(uri).path if urlparse(uri).scheme == "file" else uri
    if path.endswith(".npy"):
        return np.load(path, allow_pickle=False)
    if path.endswith(".parquet"):
        import pandas as pd
        return pd.read_parquet(path).to_numpy()
    raise ValueError(f"Unsupported data extension: {path}")


def fit_predict_persist(payload: FitPayload) -> FitResult:
    from lightgbm import LGBMClassifier
    import mlflow.lightgbm

    destination = Path(payload.destination).absolute()
    _private_parent(destination)
    X, y = _array(payload.x_uri), _array(payload.y_uri).ravel()
    if X.ndim != 2 or len(X) != len(y) or len(X) < 2 or not np.isin(y, (0, 1)).all():
        raise ValueError("LightGBM training arrays are not exact binary tabular data")
    X_train, y_train, X_val = _training_arrays(payload, X, y)
    weights = _weights(payload)
    fit_options = {}
    if payload.init_model is not None:
        initial = load_init_model(payload.init_model)
        fit_options["init_model"] = initial
    parameters = {
        "n_estimators": payload.rounds, "random_state": payload.seed,
        "verbose": -1, **weights,
    }
    if payload.training_mode == "standard":
        parameters.update({"max_depth": 6, "learning_rate": 0.1})
    model = LGBMClassifier(**parameters).fit(X_train, y_train, **fit_options)
    booster, width = classifier_booster(model)
    probabilities, importances = outputs(model, X_val, width)
    mlflow.lightgbm.save_model(
        booster, str(destination), metadata=lightgbm_metadata(width),
        pip_requirements=[
            f"lightgbm=={version('lightgbm')}", f"mlflow=={version('mlflow')}",
        ],
    )
    validate_lightgbm_flavor(destination)
    return FitResult(
        width=width, threshold=0.5, importances=importances.tolist(),
        probabilities=probabilities.tolist(), iterations=booster.current_iteration(),
    )


def inspect(operation: str, payload: ArtifactPayload) -> InspectResult:
    _, width, threshold, importances = load_artifact(operation, payload)
    return InspectResult(
        width=width, threshold=threshold, importances=importances.tolist(),
    )


def score(operation: str, payload: ScorePayload) -> ScoreResult:
    model, width, threshold, importances = load_artifact(operation, payload)
    probabilities, observed = outputs(model, _array(payload.values_uri), width)
    if not np.array_equal(importances, observed):
        raise ValueError("LightGBM importances changed between load and score")
    return ScoreResult(
        width=width, threshold=threshold, importances=importances.tolist(),
        probabilities=probabilities.tolist(),
    )


def _training_arrays(payload: FitPayload, X: np.ndarray, y: np.ndarray):
    if payload.validation_x_uri is not None:
        X_val = _array(payload.validation_x_uri)
        y_val = _array(payload.validation_y_uri or "").ravel()
        if X_val.ndim != 2 or X_val.shape[1] != X.shape[1] or len(X_val) != len(y_val):
            raise ValueError("LightGBM validation arrays are inconsistent")
        return X, y, X_val
    train, validation = _split_indices(y, payload.validation_split, payload.seed)
    return X[train], y[train], X[validation]


def _weights(payload: FitPayload) -> dict:
    values = {}
    if payload.scale_pos_weight is not None:
        values["scale_pos_weight"] = payload.scale_pos_weight
    if payload.class_weight is not None:
        values["class_weight"] = (
            {int(key): value for key, value in payload.class_weight.items()}
            if isinstance(payload.class_weight, dict) else payload.class_weight
        )
    return values


def _split_indices(y: np.ndarray, fraction: float, seed: int):
    count = max(1, int(len(y) * fraction)); split = max(1, len(y) - count)
    indices = np.arange(len(y)); train, validation = indices[:split], indices[split:]
    if len(np.unique(y[validation])) < 2 and len(np.unique(y[train])) > 1:
        np.random.default_rng(seed).shuffle(indices)
        train, validation = indices[:split], indices[split:]
    return train, validation


def _private_parent(destination: Path) -> None:
    parent = destination.parent
    if destination.exists() or destination.is_symlink():
        raise ValueError("MLflow LightGBM destination must not already exist")
    if not parent.is_dir() or parent.is_symlink() or parent.stat().st_mode & 0o077:
        raise ValueError("native destination parent must be a private directory")


__all__ = ["fit_predict_persist", "inspect", "score"]
