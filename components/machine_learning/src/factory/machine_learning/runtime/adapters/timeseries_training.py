"""Memory-backed time-series training adapter.

Implements the TimeSeriesTrainingPort protocol for development and testing.
The real LightGBM/TCN/LSTM training loop is stubbed — the adapter records
job lifecycle, config, and synthetic metrics so downstream MCP tooling can
exercise the full port surface without GPU dependencies.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from ..ports import (
    TimeSeriesModelConfig,
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
    TimeSeriesTrainingPort,
    validate_model_config_for_family,
)


class MemoryTimeSeriesTrainingAdapter:
    """In-memory time-series training backend — simulates job lifecycle."""

    def __init__(self, **kwargs: Any) -> None:
        self._jobs: dict[str, TimeSeriesTrainingJob] = {}
        self._models: dict[str, dict[str, Any]] = {}

    def train(
        self,
        model_type: TimeSeriesModelType,
        X_uri: str,
        y_uri: str,
        config: TimeSeriesTrainingConfig | None = None,
        experiment_name: str = "",
        model_config: TimeSeriesModelConfig | None = None,
    ) -> TimeSeriesTrainingJob:
        """Train a time-series model — memory backend completes synchronously."""
        validate_model_config_for_family(model_type, model_config)
        job = TimeSeriesTrainingJob(
            id=str(uuid.uuid4()),
            model_type=model_type,
            status="running",
            experiment_id=f"exp-{hashlib.sha256(experiment_name.encode()).hexdigest()[:8]}" if experiment_name else None,
            run_id=str(uuid.uuid4()),
            config=config or TimeSeriesTrainingConfig(),
        )
        # Synthetic deterministic metrics keyed by model_type so callers can assert.
        seed = (job.config.seed + hash((model_type.value, X_uri, y_uri))) & 0xFFFF
        job.metrics = {
            "auroc": 0.5 + (seed % 500) / 1000.0,
            "auprc": 0.4 + (seed % 400) / 1000.0,
            "brier": 0.1 + (seed % 100) / 1000.0,
            "lead_time_ms": float(50 + (seed % 450)),
        }
        job.model_path = f"memory://timeseries/{job.id}/{model_type.value}"
        job.status = "completed"
        self._jobs[job.id] = job
        self._models[job.id] = {
            "id": job.id,
            "model_type": model_type.value,
            "model_path": job.model_path,
            "metrics": dict(job.metrics),
            "config": {
                "window_size": job.config.window_size,
                "stride": job.config.stride,
                "batch_size": job.config.batch_size,
                "epochs": job.config.epochs,
                "learning_rate": job.config.learning_rate,
            },
            "X_uri": X_uri,
            "y_uri": y_uri,
            "created_at": job.created_at.isoformat(),
        }
        return job

    def predict(self, model_id: str, X_uri: str) -> str:
        """Score a windowed dataset — returns a JSONL URI of predictions."""
        if model_id not in self._models:
            raise KeyError(f"Model not found: {model_id}")
        # Deterministic stub: emit one zero-score prediction per X_uri byte length
        # capped at 1024 rows so callers can validate shape without GPU.
        rows = min(max(len(X_uri) * 8, 1), 1024)
        content = "\n".join(
            f'{{"score": 0.0, "window_index": {i}}}' for i in range(rows)
        )
        return f"memory://timeseries/{model_id}/predictions.jsonl"

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Return serialized model metadata, or None if missing."""
        model = self._models.get(model_id)
        return dict(model) if model is not None else None

    def list_models(self) -> list[dict[str, Any]]:
        """List all trained models with summary fields."""
        return [
            {
                "id": m["id"],
                "model_type": m["model_type"],
                "model_path": m["model_path"],
                "auroc": m["metrics"].get("auroc"),
                "created_at": m["created_at"],
            }
            for m in self._models.values()
        ]

    def compare_models(
        self, model_ids: list[str], metric: str = "auroc"
    ) -> dict[str, Any]:
        """Compare models on a single metric — returns ranked list."""
        rows: list[dict[str, Any]] = []
        for model_id in model_ids:
            model = self._models.get(model_id)
            if model is None:
                continue
            value = model["metrics"].get(metric)
            rows.append({"id": model_id, "model_type": model["model_type"], metric: value})
        rows.sort(key=lambda r: (r[metric] is None, -(r[metric] or 0.0)))
        return {
            "metric": metric,
            "models": rows,
            "best_model_id": rows[0]["id"] if rows else None,
            "count": len(rows),
        }
