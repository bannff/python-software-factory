"""Parent-safe LightGBM training orchestration through a native process port."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np

from ..native_lightgbm_contracts import FitPayload, FitRequest, FitResult
from ..native_lightgbm_port import NativeLightGBMPort
from ..passport_tree_seal import remove_staging_tree
from ..ports import TimeSeriesModelType, TimeSeriesTrainingConfig, TimeSeriesTrainingJob
from .mlflow_lightgbm import validate_lightgbm_flavor
from .native_lightgbm_process import SubprocessNativeLightGBM
from .temporal_split import temporal_split_with_shuffle_fallback
from .timeseries_metrics import compute_classification_metrics


def load_array(uri: str) -> np.ndarray:
    path = urlparse(uri).path if urlparse(uri).scheme == "file" else uri
    if path.endswith(".npy"):
        return np.load(path, allow_pickle=False)
    if path.endswith(".parquet"):
        import pandas as pd
        return pd.read_parquet(path).to_numpy()
    raise ValueError(f"Unsupported data extension: {path}")


def train_lightgbm(
    *, tracker: Any, root: Path, x_uri: str, y_uri: str,
    config: TimeSeriesTrainingConfig, experiment_name: str,
    job_id: str | None = None, effect_dir: Path | None = None,
    native_port: NativeLightGBMPort | None = None,
) -> tuple[TimeSeriesTrainingJob, dict[str, Any]]:
    X, y = load_array(x_uri), load_array(y_uri).ravel()
    job_id = job_id or str(uuid.uuid4())
    target, staging, owns_staging = _target(root, job_id, effect_dir)
    try:
        result = (native_port or SubprocessNativeLightGBM()).execute(FitRequest(
            operation="fit_predict_persist",
            payload=FitPayload(
                x_uri=x_uri, y_uri=y_uri, destination=str(target / "mlflow-model"),
                validation_split=config.validation_split, seed=config.seed,
                **_weights(config),
            ),
        ))
        if not isinstance(result, FitResult):
            raise ValueError("native_process_protocol_error: fit result kind")
        model_path = target / "mlflow-model"
        validate_lightgbm_flavor(model_path)
        _, _, _, y_val = temporal_split_with_shuffle_fallback(
            X, y, config.validation_split, config.seed,
        )
        probabilities = np.asarray(result.probabilities, dtype=float)
        if probabilities.shape != (len(y_val), 2) or result.width != X.shape[1]:
            raise ValueError("native_process_protocol_error: fit output shape")
        y_pred = np.argmax(probabilities, axis=1).astype(np.int64)
        y_score = probabilities[:, 1]
        metrics = compute_classification_metrics(y_val, y_pred, y_score)
        if owns_staging:
            final = root / job_id
            if final.exists() or final.is_symlink():
                raise ValueError("LightGBM final model directory already exists")
            os.rename(staging, final)
            target, model_path = final, final / "mlflow-model"
    except BaseException:
        if owns_staging:
            remove_staging_tree(staging)
        raise
    exp_id, run_id = _track(
        tracker, experiment_name, config, metrics, str(model_path),
    )
    record = {
        "id": job_id, "model_type": TimeSeriesModelType.lightgbm.value,
        "model_path": str(model_path), "metrics": metrics,
        "X_uri": x_uri, "y_uri": y_uri, "experiment_id": exp_id,
        "run_id": run_id, "created_at": datetime.now().isoformat(),
    }
    return TimeSeriesTrainingJob(
        id=job_id, model_type=TimeSeriesModelType.lightgbm, status="completed",
        experiment_id=exp_id, run_id=run_id, config=config, metrics=metrics,
        model_path=str(model_path), val_y_true=y_val.tolist(),
        val_y_pred=y_pred.tolist(), val_y_score=y_score.tolist(),
    ), record


def _target(root: Path, job_id: str, effect_dir: Path | None):
    if effect_dir is not None:
        target = effect_dir.absolute()
        if not target.is_dir() or target.is_symlink():
            raise ValueError("LightGBM effect directory must already exist")
        os.chmod(target, 0o700)
        return target, target, False
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".{job_id}.staging"
    remove_staging_tree(staging)
    staging.mkdir(mode=0o700)
    return staging, staging, True


def _weights(config: TimeSeriesTrainingConfig) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if "scale_pos_weight" in config.extra:
        values["scale_pos_weight"] = float(config.extra["scale_pos_weight"])
    if "class_weight" in config.extra:
        raw = config.extra["class_weight"]
        values["class_weight"] = (
            {str(key): float(value) for key, value in raw.items()}
            if isinstance(raw, dict) else raw
        )
    return values


def _track(
    tracker: Any, name: str, config: TimeSeriesTrainingConfig,
    metrics: dict[str, float], model_path: str,
) -> tuple[str | None, str | None]:
    if tracker is None:
        return None, None
    try:
        experiment_name = name or "can-ts-lightgbm"
        experiment = (
            tracker.get_experiment_by_name(experiment_name)
            or tracker.create_experiment(name=experiment_name)
        )
        run = tracker.start_run(experiment_id=experiment.id)
        tracker.log_params(run.id, {
            "model_type": "lightgbm", "n_estimators": 100, "max_depth": 6,
            "learning_rate": 0.1, "window_size": config.window_size,
            "seed": config.seed,
        })
        tracker.log_metrics(run.id, metrics)
        tracker.log_artifact(run.id, model_path)
        tracker.end_run(run.id)
        return experiment.id, run.id
    except Exception:
        return None, None


__all__ = ["load_array", "train_lightgbm"]
