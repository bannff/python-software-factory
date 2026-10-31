"""Durable MLX-native LSTM and TCN time-series training adapter."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..passport_config import configured_passport_root
from ..passport_paths import reject_symlink_ancestors
from ..ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob, validate_model_config_for_family,
)
from .mlx_checkpoint import log_to_tracker
from .mlx_identity import MLX_LIFECYCLE
from .mlx_platform import require_mlx_platform
from .temporal_split import temporal_split_with_shuffle_fallback
from .timeseries_metrics import compute_classification_metrics
from .torch_data import apply_scaler, fit_scaler_transform, load_array, to_windows

_logger = logging.getLogger(__name__)
_SUPPORTED = {TimeSeriesModelType.lstm, TimeSeriesModelType.tcn}


class MlxTimeSeriesAdapter:
    """Train MLX models and publish only sealed passport-authoritative trees."""

    def __init__(
        self, storage_root: str | Path, tracker: Any = None,
        checkpoint_store: Any = None,
    ) -> None:
        require_mlx_platform()
        self._tracker, self._checkpoint_store = tracker, checkpoint_store
        trust_root = configured_passport_root(storage_root)
        self._root = trust_root / "models" / "mlx"
        reject_symlink_ancestors(self._root)
        self._root.mkdir(parents=True, exist_ok=True)
        reject_symlink_ancestors(self._root)
        self._models: dict[str, dict[str, Any]] = {}

    def train(
        self, model_type: TimeSeriesModelType, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None, experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob:
        require_mlx_platform()
        if model_type not in _SUPPORTED:
            raise NotImplementedError(
                f"Model type '{model_type.value}' is not supported by MlxTimeSeriesAdapter"
            )
        validate_model_config_for_family(model_type, model_config)
        cfg = config or TimeSeriesTrainingConfig()
        import mlx.core as mx
        from .mlx_architecture import build_model
        from .mlx_artifact import persist_native_model
        from .mlx_data import MLXDataLoader
        from .mlx_training import train_loop

        mx.random.seed(cfg.seed)
        X = to_windows(load_array(X_uri), cfg.window_size).astype(np.float32)
        y = load_array(y_uri).ravel().astype(np.int32)
        if len(X) == 0 or len(y) == 0 or len(X) != len(y):
            raise ValueError(f"X has {len(X)} windows but y has {len(y)} labels")
        n_features = X.shape[2]
        n_classes = max(int(y.max()) + 1, 2)
        Xt, yt, Xv, yv = temporal_split_with_shuffle_fallback(
            X, y, cfg.validation_split, cfg.seed,
        )
        Xt, scaler_mean, scaler_scale = fit_scaler_transform(Xt, len(Xt))
        Xv = apply_scaler(Xv, scaler_mean, scaler_scale)
        loader = MLXDataLoader(
            Xt, yt, batch_size=cfg.batch_size, shuffle=True, seed=cfg.seed,
        )
        model = build_model(model_type, n_features, n_classes)
        mx.eval(model.parameters())
        best_params, _ = train_loop(
            model, loader, Xv, yv, cfg.epochs, cfg.early_stopping_patience,
            cfg.learning_rate,
        )
        model.update(best_params, strict=True)
        mx.eval(model.parameters())
        probabilities = np.asarray(mx.softmax(
            model(mx.array(np.ascontiguousarray(Xv)), training=False), axis=1,
        ))
        y_pred = probabilities.argmax(axis=1)
        y_score = probabilities[:, 1]
        metrics = compute_classification_metrics(yv, y_pred, y_score)
        model_path = persist_native_model(
            self._root, model, model_type, n_features, cfg.window_size, n_classes,
            scaler_mean, scaler_scale,
        )
        return self._finalize(
            model_type, cfg, metrics, model_path, X_uri, y_uri, experiment_name,
            yv, y_pred, y_score,
        )

    def _finalize(
        self, model_type: TimeSeriesModelType, cfg: TimeSeriesTrainingConfig,
        metrics: dict[str, float], model_path: Path, X_uri: str, y_uri: str,
        experiment_name: str, y_true: np.ndarray, y_pred: np.ndarray,
        y_score: np.ndarray,
    ) -> TimeSeriesTrainingJob:
        experiment_id, run_id = log_to_tracker(
            self._tracker, experiment_name, model_type, cfg, metrics, str(model_path),
        )
        job_id = str(uuid.uuid4())
        record = {
            "id": job_id, "model_type": model_type.value,
            "model_path": str(model_path), "metrics": metrics,
            "X_uri": X_uri, "y_uri": y_uri, "experiment_id": experiment_id,
            "run_id": run_id, "created_at": datetime.now().isoformat(),
        }
        self._models[job_id] = record
        return TimeSeriesTrainingJob(
            id=job_id, model_type=model_type, status="completed",
            experiment_id=experiment_id, run_id=run_id, config=cfg,
            metrics=metrics, val_y_true=y_true.tolist(),
            val_y_pred=y_pred.tolist(), val_y_score=y_score.tolist(),
            model_path=str(model_path), lifecycle_identity=MLX_LIFECYCLE,
        )

    def predict(self, model_id: str, X_uri: str) -> str:
        del model_id, X_uri
        raise KeyError(
            "Durable MLX inference requires an exact promoted ModelPassport via "
            "ml_predict_neural_passport"
        )

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        value = self._models.get(model_id)
        return dict(value) if value is not None else None

    def list_models(self) -> list[dict[str, Any]]:
        return [{
            "id": value["id"], "model_type": value["model_type"],
            "model_path": value["model_path"], "auroc": value["metrics"].get("auroc"),
            "created_at": value["created_at"],
        } for value in self._models.values()]

    def compare_models(
        self, model_ids: list[str], metric: str = "auroc",
    ) -> dict[str, Any]:
        rows = [{
            "id": key, "model_type": value["model_type"],
            metric: value["metrics"].get(metric),
        } for key, value in self._models.items() if key in model_ids]
        rows.sort(key=lambda row: (row[metric] is None, -(row[metric] or 0.0)))
        return {
            "metric": metric, "models": rows,
            "best_model_id": rows[0]["id"] if rows else None, "count": len(rows),
        }


__all__ = ["MlxTimeSeriesAdapter"]
