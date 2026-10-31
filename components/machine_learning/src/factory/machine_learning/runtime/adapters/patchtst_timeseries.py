"""PatchTST (Patch Time-Series Transformer) time-series training adapter.

Implements :class:`TimeSeriesTrainingPort` for the PatchTST architecture
(Nie et al., ICLR 2023). Training loop / checkpoint / registry plumbing
is shared with the Chronos and LNN adapters via
:mod:`transformer_training`; this file owns only the model factory
and the public surface so it stays under the 200-LOC ceiling.
"""

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
from .patchtst_models import PatchTSTClassifier
from .patchtst_native import load_scores, passport_config, save_native
from .torch_data import load_array, to_windows
from .transformer_training import train_classifier

_logger = logging.getLogger(__name__)
_SUPPORTED = {TimeSeriesModelType.patchtst}


def _build_patchtst(input_size: int, window_size: int, num_classes: int) -> PatchTSTClassifier:
    """PatchTST with 5-timestep patches, d_model=64, 3 transformer layers.

    patch_len=5 yields 10 patches for a 50-step window — the sweet
    spot for the CAN dataset: more patches means quadratic attention
    cost, fewer patches throws away the local structure PatchTST
    was designed to capture.
    """
    return PatchTSTClassifier(
        n_channels=input_size, seq_len=window_size,
        patch_len=5, d_model=64, n_heads=4, n_layers=3,
        num_classes=num_classes, dropout=0.1,
    )


class PatchTSTTimeSeriesAdapter:
    """Train a PatchTST classifier on windowed multivariate time-series."""

    def __init__(
        self, tracker: Any = None, checkpoint_store: Any = None,
        model_root: str | Path | None = None,
    ) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        root = model_root or os.environ.get("PATCHTST_TS_MODEL_DIR")
        self._root = Path(root).expanduser().absolute() if root else None
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
        self._models: dict[str, dict[str, Any]] = {}

    def _require_model_root(self) -> Path:
        if self._root is None:
            raise ValueError(
                "PatchTST deployable training requires model_root or PATCHTST_TS_MODEL_DIR"
            )
        return self._root

    def _tracker_log(
        self, experiment_name: str, cfg: TimeSeriesTrainingConfig,
        metrics: dict[str, float], model_path: str,
    ) -> tuple[str | None, str | None]:
        """Log the run to the experiment tracker (mirrors ``torch_timeseries.py``)."""
        if self._tracker is None:
            return None, None
        try:
            name = experiment_name or "can-ts-patchtst"
            exp = self._tracker.get_experiment_by_name(name) or self._tracker.create_experiment(name=name)
            run = self._tracker.start_run(experiment_id=exp.id)
            self._tracker.log_params(run.id, {
                "model_type": "patchtst", "window_size": cfg.window_size,
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
                f"Model type '{model_type.value}' is not supported by PatchTSTTimeSeriesAdapter.",
            )
        validate_model_config_for_family(model_type, model_config)
        root = self._require_model_root()
        cfg = config or TimeSeriesTrainingConfig()
        job, payload, record = train_classifier(
            model_type, _build_patchtst, X_uri, y_uri, cfg,
            "patchtst_ts_", grad_clip=1.0,
        )
        model = _build_patchtst(
            payload["input_size"], payload["window_size"], payload["num_classes"],
        )
        model.load_state_dict(payload["state_dict"], strict=True)
        model_path = save_native(
            root / record["id"], model, payload["input_size"],
            payload["window_size"], payload["num_classes"],
            payload["scaler_mean"].numpy(), payload["scaler_scale"].numpy(),
        )
        record["model_path"] = model_path
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
        probs = load_scores(record["model_path"], config, X)
        out = {"y_pred": probs.argmax(axis=1), "y_score": probs[:, 1]}
        pred_path = Path(record["model_path"]).parent / f"{record['id']}-predictions.npz"
        np.savez(pred_path, **out)
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
