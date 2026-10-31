"""Recent-activity reader for the sandbox dashboard.

Reads the shared events history through the MCP tool invoker and shapes each
entry into a dashboard activity row. Best-effort: any invoker/transport failure
degrades to an empty list rather than breaking the dashboard.
"""

from __future__ import annotations

from typing import Any

from .dashboard_format import age_label, age_minutes
from .dashboard_invoker import envelope_data, get_invoker

_ACTIVITY_TITLES = {
    "sandbox.provisioned": "Provisioned",
    "sandbox.status_observed": "Status Check",
    "sandbox.command_executed": "Command Executed",
    "sandbox.file_uploaded": "File Uploaded",
    "sandbox.file_downloaded": "File Downloaded",
    "sandbox.terminated": "Terminated",
    "sandbox.container_reaped": "Container Reaped",
}


def list_recent_activity(limit: int = 20, env_id: str | None = None) -> list[dict[str, Any]]:
    """Return recent sandbox activity from the shared events history."""
    invoker = get_invoker()
    if invoker is None:
        return []

    try:
        query_args: dict[str, Any] = {"source": "sandbox", "limit": limit}
        if env_id:
            query_args["payload_key"] = "env_id"
            query_args["payload_value"] = env_id
        result = invoker("events_query_history", **query_args)
        raw_entries = envelope_data(result).get("entries", [])
        entries = [
            entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry
            for entry in raw_entries
        ]
    except Exception:
        return []

    activity = [activity_row(entry) for entry in entries if isinstance(entry, dict)]
    return activity[:limit]


def activity_row(entry: dict[str, Any]) -> dict[str, Any]:
    """Shape a raw events-history entry into a dashboard activity row."""
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    event_type = str(entry.get("event_type", "sandbox.activity"))
    minutes = age_minutes(str(entry.get("timestamp", "")))
    return {
        "event_id": entry.get("event_id", ""),
        "event_type": event_type,
        "label": _ACTIVITY_TITLES.get(event_type, event_type.removeprefix("sandbox.").replace("_", " ").title()),
        "timestamp": entry.get("timestamp", ""),
        "age_minutes": minutes,
        "age_label": age_label(minutes),
        "env_id": payload.get("env_id", ""),
        "run_id": payload.get("run_id", ""),
        "status": payload.get("status", ""),
        "profile": payload.get("profile", ""),
        "command": payload.get("command", ""),
        "success": payload.get("success"),
        "detail": _activity_detail(event_type, payload),
        "payload": payload,
        "metadata": entry.get("metadata", {}),
    }


def _activity_detail(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "sandbox.command_executed":
        command = str(payload.get("command", ""))
        return f"{command} ({'ok' if payload.get('success') else 'failed'})" if command else "Command executed"
    if event_type == "sandbox.file_uploaded":
        return f"{payload.get('local_path', '')} -> {payload.get('remote_path', '')}".strip(" ->")
    if event_type == "sandbox.file_downloaded":
        return f"{payload.get('remote_path', '')} -> {payload.get('local_path', '')}".strip(" ->")
    if event_type == "sandbox.provisioned":
        profile = payload.get("profile")
        return f"profile {profile}" if profile else f"instance {payload.get('instance_type', '')}".strip()
    if event_type == "sandbox.terminated":
        return f"status {payload.get('status', '')}".strip()
    if event_type == "sandbox.status_observed":
        return f"status {payload.get('status', '')}".strip()
    return ""
