"""Best-effort persistence for time-series training runs.

Writes each completed :class:`TimeSeriesTrainingJob` to the storage
brick's SQLite doc store (collection ``ml_training_runs``) via the
``tool_invoker`` service — the same sanctioned cross-brick path the
evals brick uses for ``eval_results``. Idempotent doc_id
``mlrun-{job.id}`` (storage_doc_insert upserts).

Persistence is best-effort: failures are logged at warning and swallowed
so a missing storage brick never fails a training call — mirrors the
evals-enrichment pattern in ``can_keystone_helpers.py``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from factory.mcp_utils.interface import ToolResult

logger = logging.getLogger(__name__)

COLLECTION = "ml_training_runs"


def _get_invoker() -> Any:
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def build_run_record(
    job: Any, experiment_name: str = "", source: str = "mcp",
) -> dict[str, Any]:
    """Serialize a TimeSeriesTrainingJob into the canonical run record."""
    model_type = getattr(job.model_type, "value", str(job.model_type))
    cfg = job.config
    return {
        "run_id": job.id,
        "experiment_name": experiment_name or f"can-ts-{model_type}",
        "model_type": model_type,
        "status": job.status,
        "metrics": {
            k: v for k, v in dict(job.metrics or {}).items()
            if isinstance(v, (int, float))
        },
        "config": {
            "window_size": cfg.window_size, "stride": cfg.stride,
            "epochs": cfg.epochs, "seed": cfg.seed,
            "validation_split": cfg.validation_split,
        } if cfg else {},
        "model_path": job.model_path,
        "tracker_experiment_id": job.experiment_id,
        "tracker_run_id": job.run_id,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def persist_training_run(
    job: Any, experiment_name: str = "", source: str = "mcp",
) -> bool:
    """Persist a training job to the doc store. Returns True on success."""
    record = build_run_record(job, experiment_name=experiment_name, source=source)
    return _insert_record(record)


def _insert_record(record: dict[str, Any]) -> bool:
    """Best-effort doc-store insert; never raises. Returns True on success."""
    invoker = _get_invoker()
    if invoker is None:
        logger.warning("training_run_store: no tool_invoker; run %s not persisted",
                       record["run_id"])
        return False
    try:
        result = invoker(
            "storage_doc_insert",
            collection=COLLECTION,
            doc_id=f"mlrun-{record['run_id']}",
            data=record,
        )
    except Exception as exc:
        logger.warning("training_run_store: persist failed for %s: %s",
                       record["run_id"], exc)
        return False
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None:
            logger.warning("training_run_store: persist rejected for %s: %s",
                           record["run_id"], result.error)
            return False
    elif isinstance(result, dict) and result.get("ok") is False:
        logger.warning("training_run_store: persist rejected for %s: %s",
                       record["run_id"], result.get("error"))
        return False
    elif isinstance(result, dict) and result.get("error"):
        logger.warning("training_run_store: persist rejected for %s: %s",
                       record["run_id"], result["error"])
        return False
    return True


__all__ = ["COLLECTION", "build_run_record", "persist_training_run", "_insert_record"]
