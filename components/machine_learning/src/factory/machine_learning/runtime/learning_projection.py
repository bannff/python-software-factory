"""Learning-run projection helpers consumed by the MCP deterministic layer.

The MCP tools in ``mcp/deterministic.py`` expose read-only views of the
learning loop. Projection of canonical runtime events into a learning-run
shape lives here as private domain logic so the MCP layer stays a thin tool
surface. Sibling pattern: ``factory.events.runtime.learning_handlers``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from factory.mcp_utils.registry import get_service

_EVENT_TYPES: tuple[str, ...] = (
    "graph.launched", "graph.completed", "graph.failed", "reward.computed",
    "wallet.rewarded", "memory.learning_stored", "convergence.checked",
)
_METADATA_FIELDS: tuple[str, ...] = (
    "run_id", "workflow_run_id", "graph_id", "profile_id", "profile_version",
    "principal_id", "session_id", "target_app", "workflow_type", "vuln_class",
)
_DEFAULTS: dict[str, Any] = {"profile_id": "default", "profile_version": "v1", "workflow_type": "auto"}
_TIMELINE_LABELS: dict[str, str] = {
    "graph.launched": "Graph launched", "graph.completed": "Graph completed",
    "graph.failed": "Graph failed", "reward.computed": "Reward computed",
    "wallet.rewarded": "Wallet rewarded", "memory.learning_stored": "Learning stored",
    "convergence.checked": "Convergence checked",
}
_ARTIFACT_KEYS = ("reward_event_id", "transaction_id", "memory_id", "metric_id")
_STAGE_FLAGS = (
    ("convergence_checked", "checked"), ("memory_stored", "stored"),
    ("wallet_rewarded", "rewarded"), ("reward_event_id", "scored"),
    ("graph_completed_event_id", "completed"),
)


def _sort_key(timestamp: str) -> datetime:
    """Sort helper tolerant of bad or missing timestamps."""
    try:
        return datetime.fromisoformat(timestamp)
    except Exception:
        return datetime.min


def _apply_projection_update(projection: dict[str, Any], event_type: str, event: dict[str, Any]) -> None:
    """Merge one canonical event into the learning projection."""
    p, eid = event.get("payload", {}), event.get("id")
    if event_type == "graph.launched":
        projection.update(status=p.get("status", "running"), graph_launched_event_id=eid)
    elif event_type == "graph.completed":
        projection["status"] = p.get("status", projection["status"])
        projection["duration_ms"] = p.get("duration_ms", int(float(p.get("execution_time", 0)) * 1000))
        projection["graph_completed_event_id"] = eid
    elif event_type == "graph.failed":
        projection.update(status=p.get("status", "failed"), error=p.get("error"), graph_failed_event_id=eid)
    elif event_type == "reward.computed":
        projection["status"] = p.get("status", projection["status"])
        for k in ("score", "reward_value", "reward_unit"):
            projection[k] = p.get(k, projection[k])
        projection.update(verdict=p.get("verdict"), reward_event_id=eid)
    elif event_type == "wallet.rewarded":
        projection.update(wallet_event_id=eid, transaction_id=p.get("transaction_id"), wallet_id=p.get("wallet_id"))
    elif event_type == "memory.learning_stored":
        projection.update(memory_event_id=eid, memory_id=p.get("memory_id"), summary_type=p.get("summary_type"))
    elif event_type == "convergence.checked":
        projection.update(convergence_event_id=eid, converged=p.get("converged"),
                          metric_id=p.get("metric_id"), metrics_recorded=p.get("metrics_recorded"))


def _finalize_projection(projection: dict[str, Any]) -> None:
    """Derive view-friendly fields for the learning-run projection."""
    projection["event_history"] = sorted(projection.get("event_history", []),
                                         key=lambda i: _sort_key(i.get("timestamp", "")))
    projection["event_count"] = len(projection["event_history"])
    projection["wallet_rewarded"] = bool(projection.get("wallet_id") or projection.get("transaction_id"))
    projection["memory_stored"] = bool(projection.get("memory_id"))
    projection["convergence_checked"] = bool(projection.get("convergence_event_id"))
    projection["artifact_count"] = sum(1 for k in _ARTIFACT_KEYS if projection.get(k))
    projection["display_title"] = (projection.get("target_app") or projection.get("workflow_run_id")
                                   or projection.get("run_id") or "Learning Run")
    projection["display_subtitle"] = " • ".join(p for p in (
        str(projection.get("workflow_type", "")).upper() if projection.get("workflow_type") else "",
        projection.get("graph_id", ""), projection.get("profile_id", ""),
    ) if p)
    score = projection.get("score")
    projection["score_pct"] = round(float(score) * 100, 1) if score is not None else None
    projection["trend_direction"] = _trend_direction(projection)
    projection["stage"] = _learning_stage(projection)
    projection["last_event_type"] = (projection["event_history"][-1]["event_type"]
                                     if projection["event_history"] else "")
    projection["story"] = _build_story(projection)


def _seed(payload: dict[str, Any], key: str, timestamp: str) -> dict[str, Any]:
    """Seed an empty projection from the first event for a run."""
    seed = {f: payload.get(f, _DEFAULTS.get(f, "")) for f in _METADATA_FIELDS}
    seed["run_id"] = payload.get("run_id", key)
    seed["workflow_run_id"] = payload.get("workflow_run_id", payload.get("run_id", key))
    seed.update(status="unknown", score=None, reward_value=0, reward_unit="tokens",
                converged=None, duration_ms=0, event_history=[], updated_at=timestamp)
    return seed


def _events_from_result(result: Any) -> list[Any]:
    """Extract Events rows from its typed in-process or serialized v1 result."""
    if isinstance(result, dict):
        if (
            result.get("schema_version") != "v1" or result.get("ok") is not True
            or not isinstance(result.get("data"), dict)
        ):
            raise ValueError("events_query_events returned an invalid MCP result")
        events = result["data"].get("events")
    else:
        if not getattr(result, "ok", False) or getattr(result, "data", None) is None:
            return []
        events = getattr(result.data, "events", None)
    if not isinstance(events, list):
        raise ValueError("events_query_events returned an invalid event list")
    return events


def _load_learning_runs(limit: int) -> list[dict[str, Any]]:
    """Build learning-run projections by stitching canonical event payloads."""
    invoker = get_service("tool_invoker")
    if not invoker:
        return []
    projections: dict[str, dict[str, Any]] = {}
    for event_type in _EVENT_TYPES:
        listing = invoker("events_query_events", event_type=event_type, limit=limit)
        events = [
            event.model_dump(mode="json") if hasattr(event, "model_dump") else event
            for event in _events_from_result(listing)
        ]
        for event in events:
            payload = event.get("payload", {})
            timestamp = event.get("timestamp", "")
            key = payload.get("workflow_run_id") or payload.get("run_id") or event.get("id")
            projection = projections.setdefault(key, _seed(payload, key, timestamp))
            for field in _METADATA_FIELDS:
                projection[field] = payload.get(field, projection[field])
            projection["updated_at"] = max(projection["updated_at"], timestamp)
            projection["event_history"].append({
                "event_id": event.get("id"), "event_type": event_type,
                "timestamp": event.get("timestamp"), "source": event.get("source"),
            })
            _apply_projection_update(projection, event_type, event)
    for projection in projections.values():
        _finalize_projection(projection)
    return sorted(projections.values(),
                  key=lambda i: _sort_key(i.get("updated_at", "")), reverse=True)[:limit]


def _find_learning_run(run_id: str) -> dict[str, Any] | None:
    """Find one learning-loop run by run or workflow ID."""
    for item in _load_learning_runs(limit=200):
        if item.get("run_id") == run_id or item.get("workflow_run_id") == run_id:
            return item
    return None


def _learning_stage(projection: dict[str, Any]) -> str:
    """Return a human-readable learning stage."""
    if projection.get("converged") is True:
        return "converged"
    for flag, stage in _STAGE_FLAGS:
        if projection.get(flag):
            return stage
    return projection.get("status") or "unknown"


def _trend_direction(projection: dict[str, Any]) -> str:
    """Map current learning status to a compact trend direction."""
    if projection.get("converged") is True:
        return "up"
    score = projection.get("score")
    if score is None:
        return ""
    return "up" if float(score) >= 0.7 else "down"


def _build_story(projection: dict[str, Any]) -> str:
    """Summarize the learning-loop state in one sentence."""
    if projection.get("stage") == "running":
        return "Workflow launched and currently collecting graph evidence"
    if projection.get("stage") == "failed":
        err = projection.get("error")
        return f"Workflow failed before reward processing: {err}" if err else "Workflow failed before reward processing"
    fragments: list[str] = []
    if projection.get("reward_event_id"):
        fragments.append(f"reward scored at {projection.get('score_pct', 0)}% for "
                         f"{projection.get('reward_value', 0)} {projection.get('reward_unit', 'tokens')}")
    if projection.get("wallet_rewarded"):
        fragments.append(f"wallet credited via {projection.get('transaction_id', 'pending transaction')}")
    if projection.get("memory_stored"):
        fragments.append(f"learning stored as {projection.get('memory_id')}")
    if projection.get("convergence_checked"):
        fragments.append("convergence confirmed" if projection.get("converged") is True
                         else "convergence still under observation")
    return "; ".join(fragments) if fragments else "Run observed, waiting for reward and learning evidence"


def _timeline_line(event: dict[str, Any], run: dict[str, Any]) -> str:
    """Render one event-history item as a readable timeline line."""
    event_type = event.get("event_type", "event")
    label = _TIMELINE_LABELS.get(event_type, event_type)
    detail = {
        "graph.launched": f"workflow started for {run.get('display_title', run.get('run_id', 'run'))}",
        "graph.completed": f"workflow finished for {run.get('display_title', run.get('run_id', 'run'))}",
        "graph.failed": run.get("error") or "workflow execution failed",
        "reward.computed": (f"score {run.get('score_pct', 0)}% and reward "
                            f"{run.get('reward_value', 0)} {run.get('reward_unit', 'tokens')}"),
        "wallet.rewarded": f"wallet {run.get('wallet_id', 'unknown')} credited",
        "memory.learning_stored": f"memory artifact {run.get('memory_id', 'pending')} persisted",
        "convergence.checked": ("run converged" if run.get("converged") is True
                                else "run still collecting evidence"),
    }.get(event_type, event.get("source", ""))
    return f"{event.get('timestamp', '')} · {label} · {detail}"
