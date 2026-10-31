"""Native ``ncps.torch.LTC`` time-series training and warm inference adapter."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

from ..ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob, validate_model_config_for_family,
)
from .lnn_models import LNNClassifier
from .lnn_native import load_scores, passport_config, timing_artifact
from .lnn_timespans import train_lnn_with_timespans
from .torch_data import load_array, to_windows
from .transformer_training import save_and_register

_logger = logging.getLogger(__name__)
_SUPPORTED = {TimeSeriesModelType.lnn}


def _build_lnn(input_size: int, window_size: int, num_classes: int) -> LNNClassifier:
    """Build the one sealed native LTC architecture used by this lifecycle."""
    return LNNClassifier(
        input_size=input_size, hidden_size=32, n_layers=1,
        num_classes=num_classes, pool_last=4, dropout=0.1,
    )


class LnnTimeSeriesAdapter:
    """Train and warm-score LTC checkpoints with exact timing artifacts."""

    def __init__(
        self, tracker: Any = None, checkpoint_store: Any = None,
        model_root: str | Path | None = None,
    ) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        root = model_root or os.environ.get("LNN_TS_MODEL_DIR")
        self._root = Path(root).expanduser().absolute() if root else None
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
        self._models: dict[str, dict[str, Any]] = {}

    def _require_model_root(self) -> Path:
        if self._root is None:
            raise ValueError("LNN deployable training requires model_root or LNN_TS_MODEL_DIR")
        return self._root

    def _tracker_log(
        self, experiment_name: str, cfg: TimeSeriesTrainingConfig,
        metrics: dict[str, float], model_path: str,
    ) -> tuple[str | None, str | None]:
        if self._tracker is None:
            return None, None
        try:
            name = experiment_name or "can-ts-lnn"
            exp = self._tracker.get_experiment_by_name(name) or self._tracker.create_experiment(name=name)
            run = self._tracker.start_run(experiment_id=exp.id)
            self._tracker.log_params(run.id, {
                "model_type": "lnn", "window_size": cfg.window_size,
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

    def train(
        self, model_type: TimeSeriesModelType, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None, experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob:
        if model_type not in _SUPPORTED:
            raise NotImplementedError(
                f"Model type '{model_type.value}' is not supported by LnnTimeSeriesAdapter.",
            )
        validate_model_config_for_family(model_type, model_config)
        root = self._require_model_root()
        cfg = config or TimeSeriesTrainingConfig()
        auxiliary = model_config.auxiliary_uris if model_config is not None else {}
        if set(auxiliary) != {"timespans"} or not auxiliary["timespans"]:
            raise ValueError("LNN training requires exactly one explicit timespans URI")
        timespans_uri = auxiliary["timespans"]
        job, payload, record = train_lnn_with_timespans(
            _build_lnn, X_uri, y_uri, timespans_uri, cfg, grad_clip=0.5,
            job_id=str(cfg.extra.get("lifecycle_job_id") or "") or None,
        )
        model_path = save_and_register(payload, record, root)
        job.model_path = model_path
        exp_id, run_id = self._tracker_log(experiment_name, cfg, job.metrics, model_path)
        record["experiment_id"], record["run_id"] = exp_id, run_id
        job.experiment_id, job.run_id = exp_id, run_id
        self._models[record["id"]] = record
        return job

    def predict(self, model_id: str, X_uri: str) -> str:
        record = self._models.get(model_id)
        if record is None:
            raise KeyError(f"Model not found: {model_id}")
        config = passport_config(record["model_path"])
        X = to_windows(load_array(X_uri), config["window_size"]).astype(np.float32)
        timespans, scale, digest = timing_artifact(
            record["timespans_uri"], tuple(config["timing_shape"]),
        )
        if scale != config["timing_scale"] or digest != config["timing_digest"]:
            raise ValueError("LNN timing artifact disagrees with sealed checkpoint")
        probs = load_scores(record["model_path"], config, X, timespans)
        pred_path = Path(record["model_path"]).parent / "predictions.npz"
        np.savez(pred_path, y_pred=probs.argmax(axis=1), y_score=probs[:, 1])
        return pred_path.resolve().as_uri()

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        record = self._models.get(model_id)
        return dict(record) if record is not None else None

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {"id": item["id"], "model_type": item["model_type"],
             "model_path": item["model_path"], "auroc": item["metrics"].get("auroc"),
             "created_at": item["created_at"]}
            for item in self._models.values()
        ]

    def compare_models(
        self, model_ids: list[str], metric: str = "auroc",
    ) -> dict[str, Any]:
        rows = [
            {"id": model_id, "model_type": item["model_type"],
             metric: item["metrics"].get(metric)}
            for model_id in model_ids if (item := self._models.get(model_id)) is not None
        ]
        rows.sort(key=lambda row: (row[metric] is None, -(row[metric] or 0.0)))
        return {"metric": metric, "models": rows,
                "best_model_id": rows[0]["id"] if rows else None, "count": len(rows)}
