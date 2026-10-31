"""Best-effort tracker logging for fine-tuning jobs.

Complements the ``ml.finetuning.*`` events: events flow to the events
brick while the same run also lands in the configured experiment tracker
(env-resolved via ``TrackingRuntime.get_tracker()`` — memory in tests,
mlflow/tensorboard per environment). Tracker failure must never fail a
fine-tuning job: every call here is fire-and-forget, mirroring emit.py.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

FINETUNING_EXPERIMENT = "ml-finetuning"


def _tracker() -> Any | None:
    try:
        from .runtime import get_runtime
        return get_runtime().get_tracker()
    except Exception as exc:
        logger.debug("finetuning tracker unavailable: %s", exc)
        return None


def log_finetuning_run(
    job_id: str, base_model: str, method: str,
    status: str, metrics: dict[str, float] | None = None,
) -> None:
    """Start-or-log one tracker run per fine-tuning job. Fire-and-forget."""
    try:
        tracker = _tracker()
        if tracker is None:
            return
        experiment = tracker.get_experiment_by_name(FINETUNING_EXPERIMENT)
        experiment_id = (
            experiment.id if experiment
            else tracker.create_experiment(FINETUNING_EXPERIMENT).id
        )
        run_name = f"job-{job_id}-{status}"
        run = tracker.start_run(experiment_id, name=run_name)
        tracker.log_params(run.id, {"base_model": base_model, "method": method})
        clean = {
            k: float(v) for k, v in dict(metrics or {}).items()
            if isinstance(v, (int, float))
        }
        if clean:
            tracker.log_metrics(run.id, clean)
        tracker.end_run(run.id, status="completed" if status == "completed" else "failed")
    except Exception as exc:
        logger.debug("finetuning tracker logging skipped for %s: %s", job_id, exc)


__all__ = ["FINETUNING_EXPERIMENT", "log_finetuning_run"]
