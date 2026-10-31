"""Experiment-tracker logging for durable MLX training runs."""
from __future__ import annotations

import logging
from typing import Any

from ..ports import TimeSeriesModelType, TimeSeriesTrainingConfig

_logger = logging.getLogger(__name__)


def log_to_tracker(
    tracker: Any, experiment_name: str, model_type: TimeSeriesModelType,
    cfg: TimeSeriesTrainingConfig, metrics: dict[str, float], model_path: str,
) -> tuple[str | None, str | None]:
    """Log MLX identity and metrics without becoming deployment authority."""
    if tracker is None:
        return None, None
    try:
        name = experiment_name or f"can-ts-mlx-{model_type.value}"
        experiment = tracker.get_experiment_by_name(name)
        experiment = experiment or tracker.create_experiment(name=name)
        run = tracker.start_run(experiment_id=experiment.id)
        tracker.log_params(run.id, {
            "model_type": model_type.value, "window_size": cfg.window_size,
            "batch_size": cfg.batch_size, "epochs": cfg.epochs,
            "learning_rate": cfg.learning_rate, "seed": cfg.seed,
            "backend": "mlx", "framework": "mlx",
            "framework_version": "0.31.1",
            "loader": "mlx.nn.Module.load_weights",
            "artifact_format": "mlx-safetensors",
        })
        tracker.log_metrics(run.id, metrics)
        tracker.log_artifact(run.id, model_path)
        tracker.end_run(run.id)
        return experiment.id, run.id
    except Exception as exc:
        _logger.warning("tracker logging failed: %s", exc)
        return None, None


__all__ = ["log_to_tracker"]
