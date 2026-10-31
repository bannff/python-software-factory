"""Derived dashboard summary data for workflow views."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..runtime.envelope import Envelope
from ..runtime.execution.adapters import TaskStatus
from ..runtime.graph_sync import workflow_entity_id

if TYPE_CHECKING:
    from ..runtime.runtime import WorkflowRuntime


_RUN_STATUS_ORDER = ["running", "waiting", "pending", "succeeded", "failed", "cancelled"]
_TASK_STATUS_ORDER = ["running", "pending", "succeeded", "failed", "cancelled"]
_ACTIVITY_TITLES = {
    "workflow.run_started": "Run Started",
    "workflow.step_transition": "Step Transition",
    "workflow.event_emitted": "Event Emitted",
    "workflow.run_cancelled": "Run Cancelled",
    "workflow.run_failed": "Run Failed",
}
_GRAPH_TITLE_MAP = {
    "WorkflowRun": "Workflow Run",
    "WorkflowDefinition": "Workflow Definition",
    "WorkflowEvent": "Workflow Activity",
    "SandboxEnvironment": "Sandbox",
    "GameSession": "Game Session",
    "Metric": "Metric",
    "Finding": "Finding",
}


def build_dashboard_summary(runtime: "WorkflowRuntime") -> dict[str, Any]:
    registry = runtime.get_workflow_registry()
    registry_by_id = {str(item.get("id", "")): item for item in registry}
    runs, _ = runtime.storage.list_runs(
        tenant_id=None,
        workflow_id=None,
        status=None,
        limit=100,
        cursor=None,
    )
    run_rows = [run.model_dump(mode="json") for run in runs]
    activities = list_recent_activity()
    task_rows = list_executor_tasks(runtime, limit=100)
    graph_entities = list_related_graph_entities(run_ids=[str(item.get("run_id", "")) for item in run_rows])

    activity_by_run: dict[str, list[dict[str, Any]]] = {}
    for item in activities:
        run_id = str(item.get("run_id", ""))
        if run_id:
            activity_by_run.setdefault(run_id, []).append(item)

    tasks_by_run: dict[str, list[dict[str, Any]]] = {}
    for item in task_rows:
        run_id = str(item.get("run_id", ""))
        if run_id:
            tasks_by_run.setdefault(run_id, []).append(item)

    rows = [_run_row(item, registry_by_id, activity_by_run.get(str(item.get("run_id", "")), []), tasks_by_run.get(str(item.get("run_id", "")), [])) for item in run_rows]
    rows.sort(key=lambda item: (_status_rank(str(item.get("status", "pending"))), str(item.get("updated_at", ""))), reverse=False)
    task_rows.sort(key=lambda item: (_task_status_rank(str(item.get("status", "pending"))), str(item.get("task_id", ""))))

    status_counts = Counter(str(item.get("status", "pending")) for item in rows)
    task_counts = Counter(str(item.get("status", "pending")) for item in task_rows)
    series = [
        {"label": status.title(), "value": status_counts.get(status, 0)}
        for status in _RUN_STATUS_ORDER
        if status_counts.get(status, 0) or status in {"running", "waiting"}
    ]
    task_series = [
        {"label": status.title(), "value": task_counts.get(status, 0)}
        for status in _TASK_STATUS_ORDER
        if task_counts.get(status, 0) or status in {"running", "pending"}
    ]

    health = runtime.health_check()
    return {
        "overview": {
            "runs": len(rows),
            "running": status_counts.get("running", 0),
            "waiting": status_counts.get("waiting", 0),
            "failed": status_counts.get("failed", 0),
            "definitions": len(registry),
            "tasks": len(task_rows),
            "activity": len(activities),
            "graph_entities": len(graph_entities),
            "healthy": health.get("status") == "ok",
            "executor": runtime.executor.backend_name,
        },
        "series": series,
        "task_series": task_series,
        "runs": rows,
        "tasks": task_rows,
        "recent_activity": activities,
        "related_graph_entities": graph_entities,
    }


def list_recent_activity(limit: int = 20, run_id: str | None = None) -> list[dict[str, Any]]:
    invoker = _get_invoker()
    if invoker is None:
        return []
    try:
        result = invoker("events_query_history", source="workflow", limit=limit)
        entries = [entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry for entry in (result.data.entries if result and result.ok and result.data is not None else [])]
    except Exception:
        return []
    rows = [_activity_row(item) for item in entries if isinstance(item, dict)]
    if run_id:
        rows = [item for item in rows if str(item.get("run_id", "")) == run_id]
    return rows[:limit]


def list_executor_tasks(runtime: "WorkflowRuntime", run_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        tasks = runtime.executor.list_tasks(status=None, task_type=None, limit=limit)
    except Exception:
        return []
    for task in tasks:
        status = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
        current_run_id, step_id = _parse_task_identity(task.task_id)
        row = {
            "task_id": task.task_id,
            "run_id": current_run_id,
            "step_id": step_id,
            "status": status,
            "task_type": task.metadata.get("task_type", "") if isinstance(task.metadata, dict) else "",
            "result": task.result,
            "error": task.error,
            "metadata": task.metadata,
        }
        if not run_id or current_run_id == run_id:
            rows.append(row)
    return rows[:limit]


def list_related_graph_entities(
    *,
    limit: int = 16,
    run_id: str | None = None,
    run_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    invoker = _get_invoker()
    if invoker is None:
        return []

    candidates = [run_id] if run_id else [value for value in run_ids or [] if value]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for current_run_id in candidates:
            entity_result = invoker(
                "graph_graph_get_entity", entity_id=workflow_entity_id(current_run_id))
            entity = (
                entity_result.data.entity.model_dump()
                if entity_result and entity_result.ok and entity_result.data is not None
                and entity_result.data.entity else {}
            )
            rows.extend(_graph_rows_from_entity(entity, focus_run_id=current_run_id, seen=seen))
            neighbors_result = invoker(
                "graph_graph_get_neighbors",
                entity_id=workflow_entity_id(current_run_id),
                direction="both",
            )
            neighbors = (
                neighbors_result.data.neighbors
                if neighbors_result and neighbors_result.ok and neighbors_result.data is not None
                else []
            )
            for neighbor in neighbors:
                rows.extend(_graph_rows_from_entity(neighbor.model_dump(), focus_run_id=current_run_id, seen=seen))
    except Exception:
        return rows[:limit]
    return rows[:limit]


def _run_row(
    run: dict[str, Any],
    registry_by_id: dict[str, dict[str, Any]],
    activities: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    workflow_id = str(run.get("workflow_id", ""))
    workflow = registry_by_id.get(workflow_id, {})
    age_minutes = _age_minutes(str(run.get("updated_at", "")) or str(run.get("started_at", "")))
    return {
        **run,
        "workflow_name": str(workflow.get("name", workflow_id or "Workflow")),
        "workflow_tags": workflow.get("tags", []),
        "age_minutes": age_minutes,
        "age_label": _age_label(age_minutes),
        "activity_count": len(activities),
        "last_activity_type": activities[0].get("event_type", "") if activities else "",
        "last_activity_label": activities[0].get("label", "") if activities else "",
        "task_count": len(tasks),
        "entity_id": workflow_entity_id(str(run.get("run_id", ""))),
    }


def _activity_row(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    event_type = str(entry.get("event_type", "workflow.activity"))
    age_minutes = _age_minutes(str(entry.get("timestamp", "")))
    return {
        "event_id": entry.get("event_id", ""),
        "event_type": event_type,
        "label": _ACTIVITY_TITLES.get(event_type, event_type.removeprefix("workflow.").replace("_", " ").title()),
        "timestamp": entry.get("timestamp", ""),
        "age_label": _age_label(age_minutes),
        "detail": _activity_detail(event_type, payload),
        "metadata": entry.get("metadata", {}),
        **payload,
    }


def _activity_detail(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "workflow.run_started":
        return str(payload.get("workflow_name") or payload.get("workflow_id") or "")
    if event_type == "workflow.step_transition":
        if payload.get("status"):
            return f"{payload.get('step', payload.get('current_step_id', 'step'))}: {payload.get('status')}"
        if payload.get("from") and payload.get("to"):
            return f"{payload.get('from')} -> {payload.get('to')}"
    if event_type == "workflow.event_emitted":
        return str(payload.get("event_type_emitted", ""))
    if event_type == "workflow.run_cancelled":
        return str(payload.get("reason", "cancelled"))
    if event_type == "workflow.run_failed":
        return str(payload.get("error", "failed"))
    return ""


def _graph_rows_from_entity(entity: dict[str, Any], *, focus_run_id: str, seen: set[str]) -> list[dict[str, Any]]:
    entity_id = str(entity.get("id") or entity.get("entity_id") or "")
    if not entity_id or entity_id in seen:
        return []
    seen.add(entity_id)
    props = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_type = str(entity.get("type") or entity.get("entity_type") or props.get("type") or "Entity")
    title = str(props.get("workflow_name") or props.get("workflow_id") or props.get("run_id") or props.get("name") or entity_id)
    subtitle = str(props.get("status") or props.get("event_type") or entity_type)
    detail_parts = []
    for key in ("run_id", "workflow_id", "env_id", "game_id"):
        value = props.get(key)
        if value not in (None, ""):
            detail_parts.append(f"{key}={value}")
    return [{
        "entity_id": entity_id,
        "entity_type": entity_type,
        "label": _GRAPH_TITLE_MAP.get(entity_type, entity_type),
        "title": title,
        "subtitle": subtitle,
        "detail": ", ".join(detail_parts),
        "focus_run_id": focus_run_id,
        "properties": props,
    }]


def _parse_task_identity(task_id: str) -> tuple[str, str]:
    parts = task_id.split(":", 2)
    if len(parts) >= 2:
        return parts[0], parts[1]
    return task_id, ""


def _get_invoker():
    try:
        from factory.mcp_utils.interface import get_service

        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def _age_minutes(timestamp: str) -> int:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except ValueError:
        return 0


def _age_label(age_minutes: int) -> str:
    if age_minutes < 1:
        return "just now"
    if age_minutes < 60:
        return f"{age_minutes}m"
    hours = age_minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def _status_rank(status: str) -> int:
    order = {name: index for index, name in enumerate(_RUN_STATUS_ORDER)}
    return order.get(status, 99)


def _task_status_rank(status: str) -> int:
    order = {name: index for index, name in enumerate(_TASK_STATUS_ORDER)}
    return order.get(status, 99)