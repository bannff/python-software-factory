"""Secret-safe, bounded projections for Worker MCP responses."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import is_bounded_json, to_plain_json

from ..core import TaskInfo, WorkerHealth


def safe_json(value: Any, default: Any = None) -> Any:
    """Return a bounded JSON value, replacing provider objects with a safe default."""
    plain = to_plain_json(value)
    return plain if is_bounded_json(plain) else default


def health_payload(health: WorkerHealth, backends: list[str]) -> dict[str, Any]:
    """Project adapter health without exposing provider exception text."""
    backend = health.backend if health.backend in backends else (backends[0] if backends else "celery")
    queues = [
        queue[:128]
        for queue in health.queues[:256]
        if isinstance(queue, str) and queue
    ]
    return {
        "healthy": bool(health.healthy),
        "backend": backend,
        "active_tasks": max(0, int(health.active_tasks)),
        "queues": queues,
        "error": None if health.healthy else "worker_health_unavailable",
    }


def task_payload(task: TaskInfo) -> dict[str, Any]:
    """Project a task record while dropping non-JSON provider results."""
    return {
        "name": task.name,
        "queue": task.queue,
        "state": task.state,
        "result": safe_json(task.result),
    }


__all__ = ["health_payload", "safe_json", "task_payload"]
