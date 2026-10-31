"""Child-only exact LightGBM artifact validation and scoring."""
from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    from .lightgbm_flavor_contract import validate_lightgbm_flavor
    from .native_lightgbm_contracts import ArtifactPayload
except ImportError:  # Fixed-path worker execution avoids package initializers.
    from lightgbm_flavor_contract import validate_lightgbm_flavor
    from native_lightgbm_contracts import ArtifactPayload


def load_artifact(operation: str, payload: ArtifactPayload):
    """Load only an exact native Booster or fitted binary classifier."""
    source = Path(payload.source).absolute()
    if operation.endswith("mlflow"):
        import mlflow.lightgbm
        metadata = validate_lightgbm_flavor(source)
        model = mlflow.lightgbm.load_model(str(source))
        width, threshold = metadata["feature_width"], metadata["threshold"]
        require_booster(model, width)
    else:
        import joblib
        model = joblib.load(source)
        model, width = require_joblib_model(model)
        threshold = payload.threshold
    if payload.expected_width is not None and payload.expected_width != width:
        raise ValueError("loaded LightGBM feature width disagrees with passport")
    return model, width, threshold, importances(model, width)


def load_init_model(source: str):
    """Resolve an exact MLflow or legacy joblib model to its native Booster."""
    path = Path(source).absolute()
    if path.is_dir() and not path.is_symlink():
        import mlflow.lightgbm
        metadata = validate_lightgbm_flavor(path)
        model = mlflow.lightgbm.load_model(str(path))
        require_booster(model, metadata["feature_width"])
        return model
    import joblib
    model, width = require_joblib_model(joblib.load(path))
    booster = getattr(model, "booster_", model)
    require_booster(booster, width)
    return booster


def require_joblib_model(model):
    from lightgbm import Booster, LGBMClassifier
    if type(model) is Booster:
        width = model.num_feature()
        if type(width) is not int or width <= 0:
            raise ValueError("legacy LightGBM Booster feature width is invalid")
        require_booster(model, width)
        return model, width
    if type(model) is LGBMClassifier:
        booster, width = classifier_booster(model)
        return model, width
    raise ValueError("joblib artifact is not an exact native LightGBM model")


def classifier_booster(model):
    from lightgbm import Booster, LGBMClassifier
    classes = np.asarray(getattr(model, "classes_", ()))
    width = getattr(model, "n_features_in_", None)
    booster = getattr(model, "booster_", None)
    if (
        type(model) is not LGBMClassifier or type(booster) is not Booster
        or classes.shape != (2,) or not np.array_equal(classes, np.array([0, 1]))
        or getattr(model, "importance_type", None) != "split"
        or type(width) is not int or width <= 0
    ):
        raise ValueError("LightGBM classifier contract is not exact binary [0, 1]")
    require_booster(booster, width)
    return booster, width


def require_booster(booster, width: int) -> None:
    from lightgbm import Booster
    if (
        type(booster) is not Booster or booster.params.get("objective") != "binary"
        or booster.num_model_per_iteration() != 1 or booster.num_feature() != width
        or booster.current_iteration() <= 0
    ):
        raise ValueError("loaded LightGBM Booster contract is not exact binary")


def outputs(model, values: np.ndarray, width: int):
    inputs = np.asarray(values)
    if inputs.ndim != 2 or inputs.shape[1] != width:
        raise ValueError("LightGBM input width disagrees with sealed metadata")
    if hasattr(model, "predict_proba"):
        probabilities = np.asarray(model.predict_proba(inputs), dtype=float)
        predictions = np.asarray(model.predict(inputs))
    else:
        positive = np.asarray(model.predict(inputs, num_iteration=-1, raw_score=False))
        probabilities = np.column_stack((1.0 - positive, positive))
        predictions = np.argmax(probabilities, axis=1)
    observed = importances(model, width)
    if (
        probabilities.shape != (len(inputs), 2)
        or not np.isfinite(probabilities).all()
        or np.any((probabilities < 0.0) | (probabilities > 1.0))
        or not np.allclose(probabilities.sum(axis=1), 1.0, rtol=0, atol=1e-9)
        or not np.array_equal(predictions, np.argmax(probabilities, axis=1))
    ):
        raise ValueError("LightGBM probabilities violate the binary contract")
    return probabilities, observed


def importances(model, width: int) -> np.ndarray:
    raw = (
        model.feature_importances_ if hasattr(model, "feature_importances_")
        else model.feature_importance(importance_type="split")
    )
    values = np.asarray(raw, dtype=float)
    if values.shape != (width,) or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("LightGBM feature importances violate the sealed contract")
    return values


__all__ = [
    "classifier_booster", "load_artifact", "load_init_model", "outputs",
    "require_booster",
]
