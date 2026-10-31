"""Durable native Chronos-2 pooled CAN-classifier training adapter."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..chronos_acquisition import validate_chronos_backbone_ref
from ..chronos_acquisition_evidence import validate_acquisition_document
from ..passport_config import resolve_chronos_roots
from ..passport_snapshot import copy_verified_artifact
from ..passport_tree_seal import remove_staging_tree
from ..ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob, validate_model_config_for_family,
)
from .chronos_artifact import save_probe
from .chronos_embedding import train_probe
from .chronos_identity import exact_lora_config
from .chronos_native import seal_content_addressed
from .chronos_pipeline import load_local_pipeline

_logger = logging.getLogger(__name__)


class ChronosTimeSeriesAdapter:
    """Train frozen/LoRA probes only from an exact sealed local backbone."""

    def __init__(
        self, storage_root: str | Path, tracker: Any = None,
        checkpoint_store: Any = None,
    ) -> None:
        self._tracker = tracker
        self._checkpoint_store = checkpoint_store
        roots = resolve_chronos_roots(storage_root)
        self._trust_root, self._root = roots.trust_root, roots.model_root
        self._models: dict[str, dict[str, Any]] = {}

    def train(
        self, model_type: TimeSeriesModelType, X_uri: str, y_uri: str,
        config: TimeSeriesTrainingConfig | None = None, experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob:
        if model_type is not TimeSeriesModelType.chronos:
            raise NotImplementedError(f"Model type '{model_type.value}' is not Chronos")
        validate_model_config_for_family(model_type, model_config)
        assert model_config is not None and model_config.local_backbone_ref is not None
        if model_config.lora:
            assert model_config.lora_config is not None
            exact_lora_config(model_config.lora_config.to_runtime())
        backbone_ref = model_config.local_backbone_ref
        validate_chronos_backbone_ref(backbone_ref, self._trust_root)
        cfg = config or TimeSeriesTrainingConfig()
        job_id = str(cfg.extra.get("lifecycle_job_id") or uuid.uuid4())
        staging = self._root / f".{job_id}.staging"
        try:
            staging.mkdir(parents=True, exist_ok=False)
            copy_verified_artifact(backbone_ref, self._trust_root, staging / "backbone")
            validate_acquisition_document(staging / "backbone")
            pipeline = load_local_pipeline(staging / "backbone")
            lora_config = (
                model_config.lora_config.to_runtime()
                if model_config.lora_config is not None else None
            )
            head, metrics, extra = train_probe(
                pipeline, staging / "adapter", X_uri, y_uri, cfg.window_size,
                cfg.epochs, cfg.batch_size, cfg.learning_rate, cfg.validation_split,
                cfg.seed, cfg.early_stopping_patience, model_config.lora, lora_config,
            )
            save_probe(
                staging, head, d_model=extra["d_model"],
                input_size=extra["input_size"], window_size=cfg.window_size,
                num_classes=extra["num_classes"], scaler_mean=extra["scaler_mean"],
                scaler_scale=extra["scaler_scale"],
                adapter_mode=extra["adapter_mode"], lora_config=extra["lora_config"],
            )
            model_dir = seal_content_addressed(staging, self._root)
        except Exception:
            remove_staging_tree(staging)
            raise
        experiment_id, run_id = self._tracker_log(
            experiment_name, cfg, metrics, str(model_dir),
        )
        record = {
            "id": job_id, "model_type": "chronos", "model_path": str(model_dir),
            "metrics": metrics, "X_uri": X_uri, "y_uri": y_uri,
            "experiment_id": experiment_id, "run_id": run_id,
            "lora": model_config.lora, "created_at": datetime.now().isoformat(),
        }
        self._models[job_id] = record
        return TimeSeriesTrainingJob(
            id=job_id, model_type=model_type, status="completed",
            experiment_id=experiment_id, run_id=run_id, config=cfg,
            metrics=metrics, val_y_true=extra["val_y_true"],
            val_y_pred=extra["val_y_pred"], val_y_score=extra["val_y_score"],
            model_path=str(model_dir),
        )

    def predict(self, model_id: str, X_uri: str) -> str:
        if model_id not in self._models:
            raise KeyError(f"Model not found: {model_id}")
        raise KeyError(
            "Chronos inference requires an exact promoted ModelPassport via "
            "ml_predict_neural_passport"
        )

    def _tracker_log(
        self, name: str, cfg: TimeSeriesTrainingConfig,
        metrics: dict[str, float], model_path: str,
    ) -> tuple[str | None, str | None]:
        if self._tracker is None:
            return None, None
        try:
            experiment = self._tracker.get_experiment_by_name(name or "can-ts-chronos")
            experiment = experiment or self._tracker.create_experiment(
                name=name or "can-ts-chronos",
            )
            run = self._tracker.start_run(experiment_id=experiment.id)
            self._tracker.log_params(run.id, {
                "model_type": "chronos", "window_size": cfg.window_size,
                "batch_size": cfg.batch_size, "epochs": cfg.epochs,
                "learning_rate": cfg.learning_rate, "seed": cfg.seed,
            })
            self._tracker.log_metrics(run.id, metrics)
            self._tracker.log_artifact(run.id, model_path)
            self._tracker.end_run(run.id)
            return experiment.id, run.id
        except Exception as exc:
            _logger.warning("tracker logging failed: %s", exc)
            return None, None

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        record = self._models.get(model_id)
        return dict(record) if record is not None else None

    def list_models(self) -> list[dict[str, Any]]:
        return [{
            "id": value["id"], "model_type": value["model_type"],
            "model_path": value["model_path"], "auroc": value["metrics"].get("auroc"),
            "created_at": value["created_at"],
        } for value in self._models.values()]

    def compare_models(
        self, model_ids: list[str], metric: str = "auroc",
    ) -> dict[str, Any]:
        rows = [
            {"id": key, "model_type": value["model_type"], metric: value["metrics"].get(metric)}
            for key, value in self._models.items() if key in model_ids
        ]
        rows.sort(key=lambda row: (row[metric] is None, -(row[metric] or 0.0)))
        return {
            "metric": metric, "models": rows,
            "best_model_id": rows[0]["id"] if rows else None, "count": len(rows),
        }


__all__ = ["ChronosTimeSeriesAdapter"]
