"""Read model-training runs from the storage-brick doc store.

Canonical read path for the ML dashboard — mirrors the evals brick's
``doc_store_reader.py``. Reads collection ``ml_training_runs`` via the
``tool_invoker`` service and computes per-experiment trend/regression
signals on read: ``metric_delta``, ``trend_direction``,
``regression_state`` (baseline/improved/regressed/steady) and
``previous_run_id`` chained per experiment.

The primary comparison metric is picked per run: ``auroc`` when
present, else ``f1``, else ``accuracy`` — surfaced as
``primary_metric`` / ``primary_value`` so the view can label it.
"""
from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import ToolResult

from .training_run_store import COLLECTION

logger = logging.getLogger(__name__)

_PRIMARY_CANDIDATES = ("auroc", "f1", "accuracy")
_DELTA_EPSILON = 0.01


def _get_invoker() -> Any:
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def _is_valid_run_shape(data: dict[str, Any]) -> bool:
    """Guard against malformed/legacy docs polluting the collection."""
    return bool(data.get("run_id")) and bool(data.get("model_type")) \
        and isinstance(data.get("metrics"), dict)


def _primary_metric(metrics: dict[str, Any]) -> tuple[str, float]:
    for name in _PRIMARY_CANDIDATES:
        value = metrics.get(name)
        if isinstance(value, (int, float)):
            return name, float(value)
    for name, value in metrics.items():
        if isinstance(value, (int, float)):
            return name, float(value)
    return "", 0.0


def list_training_runs() -> list[dict[str, Any]]:
    """List all training runs, newest first, with trend/regression signals."""
    invoker = _get_invoker()
    if invoker is None:
        logger.warning("training_run_reader.list_training_runs: no tool_invoker")
        return []
    try:
        result = invoker("storage_doc_find", collection=COLLECTION, query={}, limit=500)
    except Exception as exc:
        logger.warning("training_run_reader.list_training_runs failed: %s", exc)
        return []

    if isinstance(result, ToolResult):
        if not result.ok or result.data is None:
            return []
        documents = getattr(result.data, "documents", [])
        records = [document.data for document in documents]
    else:
        if not isinstance(result, dict) or result.get("ok") is False:
            return []
        payload = result.get("data") if result.get("ok") is True else result
        documents = payload.get("documents", []) if isinstance(payload, dict) else []
        records = [document.get("data", document) if isinstance(document, dict) else None for document in documents]
    runs_raw: list[dict[str, Any]] = []
    for data in records:
        if isinstance(data, dict) and _is_valid_run_shape(data):
            runs_raw.append(data)
    runs_raw.sort(key=lambda r: r.get("timestamp", ""))

    previous_by_experiment: dict[str, dict[str, Any]] = {}
    enriched_runs: list[dict[str, Any]] = []
    for run in runs_raw:
        experiment_name = str(run.get("experiment_name", ""))
        metric_name, metric_value = _primary_metric(run.get("metrics", {}))
        previous = previous_by_experiment.get(experiment_name)

        metric_delta = 0.0
        trend_direction = "flat"
        regression_state = "baseline"
        if previous is not None:
            metric_delta = round(metric_value - float(previous.get("primary_value", 0.0)), 3)
            if metric_delta > _DELTA_EPSILON:
                trend_direction, regression_state = "up", "improved"
            elif metric_delta < -_DELTA_EPSILON:
                trend_direction, regression_state = "down", "regressed"
            else:
                regression_state = "steady"

        enriched = {
            "run_id": run.get("run_id", ""),
            "experiment_name": experiment_name,
            "model_type": run.get("model_type", ""),
            "status": run.get("status", ""),
            "source": run.get("source", "mcp"),
            "timestamp": run.get("timestamp", ""),
            "metrics": run.get("metrics", {}),
            "config": run.get("config", {}),
            "model_path": run.get("model_path", ""),
            "primary_metric": metric_name,
            "primary_value": round(metric_value, 3),
            "previous_run_id": previous.get("run_id") if previous else None,
            "metric_delta": metric_delta,
            "trend_direction": trend_direction,
            "regression_state": regression_state,
        }
        enriched_runs.append(enriched)
        previous_by_experiment[experiment_name] = enriched

    return list(reversed(enriched_runs))


def get_training_run(run_id: str) -> dict[str, Any] | None:
    """Load a full training-run record by ID (raw doc, no enrichment)."""
    invoker = _get_invoker()
    if invoker is None:
        return None
    try:
        result = invoker("storage_doc_get", collection=COLLECTION, doc_id=f"mlrun-{run_id}")
    except Exception as exc:
        logger.warning("training_run_reader.get_training_run(%s) failed: %s", run_id, exc)
        return None
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None or not result.data.found:
            return None
        data = result.data.data
    else:
        if not isinstance(result, dict) or result.get("ok") is False:
            return None
        payload = result.get("data") if result.get("ok") is True else result
        if not isinstance(payload, dict) or payload.get("found") is False:
            return None
        data = payload.get("data", payload)
    if not isinstance(data, dict) or not _is_valid_run_shape(data):
        return None
    return data


__all__ = ["get_training_run", "list_training_runs"]
