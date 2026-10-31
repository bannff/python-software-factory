"""Dashboard readers for canonical immutable Evals artifact documents."""
from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import ToolResult

from ..run_record_contract import (
    EVALUATION_RUN_RECORD_KIND,
    EVAL_RESULTS_COLLECTION,
    SCHEMA_VERSION,
    document_id,
    expected_terminal_state,
    semantic_content_hash,
)

logger = logging.getLogger(__name__)
_REQUIRED_AGGREGATES = (
    "pass_rate", "avg_score", "total_cases", "passed_cases", "failed_cases",
)


def _has_exact_hash(data: dict[str, Any]) -> bool:
    try:
        return data.get("content_hash") == semantic_content_hash(data)
    except (TypeError, ValueError):
        return False


def _valid_run(data: Any, wrapper_id: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict) or not isinstance(wrapper_id, str):
        return None
    run_id = data.get("run_id")
    kind = data.get("record_kind")
    if (
        data.get("schema_version") != SCHEMA_VERSION
        or kind != EVALUATION_RUN_RECORD_KIND
        or data.get("terminal_state") != expected_terminal_state(kind)
        or not isinstance(run_id, str)
        or not run_id
        or wrapper_id != document_id(run_id, kind)
        or not data.get("experiment_name")
        or any(field not in data or data[field] is None for field in _REQUIRED_AGGREGATES)
        or not _has_exact_hash(data)
    ):
        return None
    return data


def _get_invoker():
    from factory.mcp_utils.interface import get_service
    return get_service("tool_invoker")


def list_runs() -> list[dict[str, Any]]:
    """List validated schema-v2 artifact runs, newest first."""
    invoker = _get_invoker()
    if invoker is None:
        return []
    try:
        result = invoker(
            "storage_doc_find", collection=EVAL_RESULTS_COLLECTION, query={}, limit=500,
        )
    except Exception as exc:
        logger.warning("doc_store_reader.list_runs failed: %s", exc)
        return []
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None:
            return []
        wrappers = result.data.documents
        records = [(wrapper.data, wrapper.id) for wrapper in wrappers]
    else:
        if not isinstance(result, dict) or result.get("ok") is False:
            return []
        payload = result.get("data") if result.get("ok") is True else result
        if not isinstance(payload, dict):
            return []
        records = [
            (wrapper.get("data", wrapper), wrapper.get("id"))
            for wrapper in payload.get("documents", [])
            if isinstance(wrapper, dict)
        ]
    runs = []
    for data, wrapper_id in records:
        valid = _valid_run(data, wrapper_id)
        if valid is not None:
            runs.append(valid)
    runs.sort(key=lambda run: run.get("timestamp", ""))
    previous_by_experiment: dict[str, dict[str, Any]] = {}
    enriched: list[dict[str, Any]] = []
    for run in runs:
        experiment = str(run["experiment_name"])
        previous = previous_by_experiment.get(experiment)
        pass_rate = float(run["pass_rate"])
        avg_score = float(run["avg_score"])
        pass_delta = round(pass_rate - float(previous["pass_rate"]), 3) if previous else 0.0
        score_delta = round(avg_score - float(previous["avg_score"]), 3) if previous else 0.0
        trend = "up" if pass_delta > 0.01 else "down" if pass_delta < -0.01 else "flat"
        state = "baseline" if previous is None else "improved" if trend == "up" else "regressed" if trend == "down" else "steady"
        row = {
            "run_id": run["run_id"], "experiment_name": experiment, "timestamp": run.get("timestamp", ""),
            "completion_status": "completed" if run.get("timestamp") else "completed_time_unavailable",
            "verdict": run.get("verdict", "—"), "source": run.get("source", "experiment"),
            "pass_rate": pass_rate, "avg_score": avg_score, "total_cases": int(run["total_cases"]),
            "passed_cases": int(run["passed_cases"]), "failed_cases": int(run["failed_cases"]),
            "duration_ms": float(run.get("duration_ms", 0) or 0), "evaluators_used": run.get("evaluators_used", []),
            "case_scores": run.get("case_scores", []), "agent": run.get("agent", {}),
            "previous_run_id": previous.get("run_id") if previous else None,
            "pass_rate_delta": pass_delta, "avg_score_delta": score_delta,
            "trend_direction": trend, "regression_state": state,
        }
        enriched.append(row)
        previous_by_experiment[experiment] = row
    return list(reversed(enriched))


def get_run(run_id: str) -> dict[str, Any] | None:
    """Load a validated schema-v2 artifact by run ID."""
    invoker = _get_invoker()
    if invoker is None:
        return None
    expected_id = document_id(run_id, EVALUATION_RUN_RECORD_KIND)
    try:
        result = invoker(
            "storage_doc_get", collection=EVAL_RESULTS_COLLECTION, doc_id=expected_id,
        )
    except Exception as exc:
        logger.warning("doc_store_reader.get_run(%s) failed: %s", run_id, exc)
        return None
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None or not result.data.found:
            return None
        return _valid_run(result.data.data, result.data.id)
    if not isinstance(result, dict) or result.get("ok") is False:
        return None
    payload = result.get("data") if result.get("ok") is True else result
    if not isinstance(payload, dict) or payload.get("found") is False:
        return None
    data = payload.get("data", payload)
    wrapper_id = payload.get("id", expected_id if "data" not in payload else None)
    return _valid_run(data, wrapper_id)
