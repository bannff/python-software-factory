"""Derived dashboard summary data for the sandbox views.

Thin orchestrator: it pulls fleet data from the runtime, delegates activity and
graph context to the reader modules, and row/format shaping to
``dashboard_format``. The reader entrypoints are re-exported here so existing
imports (``mcp.views``) keep working unchanged.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, TYPE_CHECKING

from .dashboard_activity import list_recent_activity
from .dashboard_format import (
    _STATUS_ORDER,
    adapter_name,
    environment_row,
    profile_row,
    status_rank,
)
from .dashboard_graph import list_related_graph_entities

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime

__all__ = [
    "build_dashboard_summary",
    "list_recent_activity",
    "list_related_graph_entities",
]


def build_dashboard_summary(runtime: "SandboxRuntime") -> dict[str, Any]:
    """Aggregate sandbox runtime data into dashboard-friendly structures."""
    from ..runtime.profiles import BUILTIN_PROFILES

    environments = runtime.list_environments()
    health = runtime.health_check()
    profiles = BUILTIN_PROFILES
    activities = list_recent_activity()
    graph_entities = list_related_graph_entities()
    env_rows = [environment_row(env.model_dump(), profiles) for env in environments]

    _attach_activity_summary(env_rows, activities)
    env_rows.sort(key=lambda item: (status_rank(item["status"]), item.get("created_at", "")), reverse=False)

    status_counts = Counter(str(item.get("status", "unknown")) for item in env_rows)
    running = status_counts.get("running", 0)
    provisioning = status_counts.get("provisioning", 0) + status_counts.get("pending", 0)
    issues = status_counts.get("error", 0) + status_counts.get("unknown", 0)

    series = [
        {"label": status.title(), "value": status_counts.get(status, 0)}
        for status in _STATUS_ORDER
        if status_counts.get(status, 0) or status in {"running", "provisioning", "error"}
    ]

    profile_rows = [profile_row(name, profile, env_rows) for name, profile in profiles.items()]
    profile_rows.sort(key=lambda item: (-int(item["active_count"]), item["name"]))

    return {
        "overview": {
            "environments": len(env_rows),
            "running": running,
            "provisioning": provisioning,
            "issues": issues,
            "profiles": len(profile_rows),
            "activity": len(activities),
            "graph_entities": len(graph_entities),
            "healthy": bool(health.get("healthy", False)),
            "adapter": adapter_name(health),
        },
        "series": series,
        "environments": env_rows,
        "recent_activity": activities,
        "related_graph_entities": graph_entities,
        "profiles": profile_rows,
    }


def _attach_activity_summary(
    env_rows: list[dict[str, Any]], activities: list[dict[str, Any]],
) -> None:
    """Annotate each environment row with its most recent activity, in place."""
    activity_by_env: dict[str, list[dict[str, Any]]] = {}
    for activity in activities:
        env_id = str(activity.get("env_id", ""))
        if env_id:
            activity_by_env.setdefault(env_id, []).append(activity)

    for row in env_rows:
        env_activity = activity_by_env.get(str(row.get("env_id", "")), [])
        row["activity_count"] = len(env_activity)
        row["last_activity_type"] = env_activity[0].get("event_type") if env_activity else ""
        row["last_activity_label"] = env_activity[0].get("label") if env_activity else ""
        row["last_activity_at"] = env_activity[0].get("timestamp") if env_activity else ""
