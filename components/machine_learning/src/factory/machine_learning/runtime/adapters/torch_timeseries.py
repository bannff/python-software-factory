"""PyTorch-backed LSTM / TCN time-series training adapter."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob, validate_model_config_for_family,
)
from .temporal_split import temporal_split_with_shuffle_fallback
from .timeseries_metrics import compute_classification_metrics
from .torch_data import apply_scaler, fit_scaler_transform, load_array, to_windows

_logger = logging.getLogger(__name__)
_SUPPORTED = {TimeSeriesModelType.lstm, TimeSeriesModelType.tcn}


class TorchTimeSeriesAdapter:
    """Train LSTM / TCN time-series classifiers on windowed data."""

    def __init__(
        self, tracker: Any = None, checkpoint_store: Any = None,
        model_root: str | Path | None = None,
    ) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        root = model_root or os.environ.get("TORCH_TS_MODEL_DIR")
        self._root = Path(root).expanduser().absolute() if root else None
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
        self._models: dict[str, dict[str, Any]] = {}

    def _require_model_root(self) -> Path:
        if self._root is None:
            raise ValueError("Torch training requires model_root or TORCH_TS_MODEL_DIR")
        return self._root

    def _tracker_log(
        self, experiment_name: str, model_type: TimeSeriesModelType,
        cfg: TimeSeriesTrainingConfig, metrics: dict[str, float], model_path: str,
    ) -> tuple[str | None, str | None]:
        if self._tracker is None:
            return None, None
        try:
            name = experiment_name or f"can-ts-{model_type.value}"
            exp = self._tracker.get_experiment_by_name(name) or self._tracker.create_experiment(name=name)
            run = self._tracker.start_run(experiment_id=exp.id)
            self._tracker.log_params(run.id, {
                "model_type": model_type.value, "window_size": cfg.window_size,
                "batch_size": cfg.batch_size, "epochs": cfg.epochs,
                "learning_rate": cfg.learning_rate, "seed": cfg.seed,
            })
            self._tracker.log_metrics(run.id, metrics)
            self._tracker.log_artifact(run.id, model_path)
            self._tracker.end_run(run.id)
            return exp.id, run.id
        except Exception as exc:
            _logger.warning("tracker logging failed: %s", exc)
            return None, None

    def _persist(
        self, model_type: TimeSeriesModelType, n_features: int, n_classes: int,
        window_size: int, state: dict[str, Any], metrics: dict[str, float],
        cfg: TimeSeriesTrainingConfig, X_uri: str, y_uri: str, experiment_name: str,
        scaler_mean: np.ndarray, scaler_scale: np.ndarray, y_true: np.ndarray,
        y_pred: np.ndarray, y_score: np.ndarray,
    ) -> TimeSeriesTrainingJob:
        """Save checkpoint, log to tracker, register record, return the job."""
        import torch
        from .torch_native import checkpoint_payload

        job_id = str(uuid.uuid4())
        model_dir = self._require_model_root() / job_id
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = str(model_dir / "model.pt")
        torch.save(checkpoint_payload(
            model_type, state, n_features, window_size, n_classes,
            scaler_mean, scaler_scale,
        ), model_path)
        exp_id, run_id = self._tracker_log(experiment_name, model_type, cfg, metrics, model_path)
        record = {
            "id": job_id, "model_type": model_type.value, "model_path": model_path,
            "metrics": metrics, "X_uri": X_uri, "y_uri": y_uri,
            "experiment_id": exp_id, "run_id": run_id,
            "created_at": datetime.now().isoformat(),
        }
        self._models[job_id] = record
        return TimeSeriesTrainingJob(
            id=job_id, model_type=model_type, status="completed",
            experiment_id=exp_id, run_id=run_id, config=cfg,
            metrics=metrics, model_path=model_path,
            val_y_true=y_true.astype(float).tolist(),
            val_y_pred=y_pred.astype(float).tolist(), val_y_score=y_score.tolist(),
        )

    def train(
        self, model_type: TimeSeriesModelType, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None, experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob:
        if model_type not in _SUPPORTED:
            raise NotImplementedError(
                f"Model type '{model_type.value}' is not supported by TorchTimeSeriesAdapter.",
            )
        validate_model_config_for_family(model_type, model_config)
        self._require_model_root()
        import torch
        from torch import nn, optim
        from torch.utils.data import DataLoader, TensorDataset
        from .torch_training import build_model, train_loop
        cfg = config or TimeSeriesTrainingConfig()
        torch.manual_seed(cfg.seed)
        np.random.seed(cfg.seed)
        X = to_windows(load_array(X_uri), cfg.window_size).astype(np.float32)
        y = load_array(y_uri).ravel().astype(np.int64)
        n_samples, _, n_features = X.shape
        if n_samples != len(y):
            raise ValueError(f"X has {n_samples} windows but y has {len(y)} labels")
        n_classes = max(int(y.max()) + 1, 2)  # >=2 keeps CrossEntropyLoss happy
        Xt, yt, Xv, yv = temporal_split_with_shuffle_fallback(
            X, y, cfg.validation_split, cfg.seed,
        )
        Xt, scaler_mean, scaler_scale = fit_scaler_transform(Xt, len(Xt))
        Xv = apply_scaler(Xv, scaler_mean, scaler_scale)
        model = build_model(model_type, input_size=n_features, num_classes=n_classes)
        loader = DataLoader(
            TensorDataset(torch.from_numpy(Xt), torch.from_numpy(yt)),
            batch_size=cfg.batch_size, shuffle=True,
        )
        best_state = train_loop(
            model, loader, torch.from_numpy(Xv), torch.from_numpy(yv),
            nn.CrossEntropyLoss(), optim.Adam(model.parameters(), lr=cfg.learning_rate),
            cfg.epochs, cfg.early_stopping_patience,
        )
        model.load_state_dict(best_state)
        model.eval()
        with torch.no_grad():
            probs = torch.softmax(model(torch.from_numpy(Xv)), dim=1).numpy()
        y_pred, y_score = probs.argmax(axis=1), (probs[:, 1] if probs.shape[1] > 1 else probs[:, 0])
        metrics = compute_classification_metrics(yv, y_pred, y_score)
        return self._persist(
            model_type, n_features, n_classes, cfg.window_size, best_state,
            metrics, cfg, X_uri, y_uri, experiment_name, scaler_mean, scaler_scale,
            yv, y_pred, y_score,
        )

    def predict(self, model_id: str, X_uri: str) -> str:
        record = self._models.get(model_id)
        if record is None:
            raise KeyError(f"Model not found: {model_id}")
        from .torch_native import load_scores, passport_config

        config = passport_config(record["model_path"])
        X = to_windows(load_array(X_uri), config["window_size"])
        probs = load_scores(
            record["model_path"], record["model_type"], config, X.astype(np.float32),
        )
        y_pred, y_score = probs.argmax(axis=1), probs[:, 1]
        pred_path = Path(record["model_path"]).parent / "predictions.npz"
        np.savez(pred_path, y_pred=y_pred, y_score=y_score)
        return f"file://{pred_path}"

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        rec = self._models.get(model_id)
        return dict(rec) if rec is not None else None

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {"id": m["id"], "model_type": m["model_type"], "model_path": m["model_path"],
             "auroc": m["metrics"].get("auroc"), "created_at": m["created_at"]}
            for m in self._models.values()
        ]

    def compare_models(
        self, model_ids: list[str], metric: str = "auroc",
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for model_id in model_ids:
            m = self._models.get(model_id)
            if m is None:
                continue
            rows.append({"id": model_id, "model_type": m["model_type"],
                         metric: m["metrics"].get(metric)})
        rows.sort(key=lambda r: (r[metric] is None, -(r[metric] or 0.0)))
        return {
            "metric": metric, "models": rows,
            "best_model_id": rows[0]["id"] if rows else None,
            "count": len(rows),
        }
