"""Durable background-run activity binding on existing AG-UI primitives."""
from __future__ import annotations

import time
from typing import Any

from ._ag_ui_activity_deltas import build_close_content, build_open_content, workflow_to_delta
from .ag_ui_mapper import AGUIEventType

_TOOL = "agent_spawn_background"
_TERMINAL = {
    "workflow.run_succeeded": "completed",
    "workflow.run_failed": "failed",
    "workflow.run_cancelled": "cancelled",
}


def bind_background_result(chat_event: Any, active: Any, state: Any) -> list[dict] | None:
    if active.tool_name != _TOOL:
        return None
    payload = getattr(chat_event, "payload", None)
    run_id = payload.get("run_id") if isinstance(payload, dict) else None
    if not isinstance(run_id, str) or not run_id:
        return []
    active.run_id = run_id
    state.runs_by_run_id[run_id] = active
    if active in state.pending_unbound:
        state.pending_unbound.remove(active)
    content = build_open_content(active.tool_name, run_id, active.started_at)
    content["agent_id"] = str(payload.get("agent_id") or "")
    return [_snapshot(active, content, replace=True)]


def map_background_workflow(raw: dict, active: Any, state: Any) -> list[dict] | None:
    if active.tool_name != _TOOL:
        return None
    event_type = raw.get("event_type")
    payload = raw.get("payload") or {}
    if event_type == "workflow.attempt_started":
        return workflow_to_delta(active, "graph.node_start", {
            **payload, "node_id": payload.get("agent_id") or payload.get("step_id"),
        })
    if event_type == "workflow.attempt_completed":
        mapped = "graph.node_error" if payload.get("status") == "failed" else "graph.node_stop"
        return workflow_to_delta(active, mapped, {
            **payload, "node_id": payload.get("agent_id") or payload.get("step_id"),
        })
    if event_type not in _TERMINAL:
        return None
    content = build_close_content(
        active, event_type != "workflow.run_succeeded", time.time(), payload,
    )
    content["status"] = _TERMINAL[event_type]
    state.runs_by_run_id.pop(active.run_id, None)
    state.runs_by_tool_call_id.pop(active.tool_call_id, None)
    return [_snapshot(active, content, replace=True)]


def _snapshot(active: Any, content: dict, *, replace: bool) -> dict:
    return {
        "type": AGUIEventType.ACTIVITY_SNAPSHOT,
        "messageId": f"subagent:{active.tool_call_id}",
        "activityType": active.activity_type, "content": content,
        "replace": replace, "timestamp": time.time(),
    }


__all__ = ["bind_background_result", "map_background_workflow"]
