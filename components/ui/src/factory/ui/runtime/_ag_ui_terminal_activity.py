"""Devtools command events to strict Terminal activity content/deltas."""
from __future__ import annotations

import time
from typing import Any

from .ag_ui_activity_models import TerminalCommandActivity
from .ag_ui_mapper import AGUIEventType


def open_content(run_id: str, started_at: float) -> dict[str, Any]:
    return TerminalCommandActivity(
        run_id=run_id, status="running", started_at=started_at,
    ).model_dump(mode="json")


def close_content(active: Any, is_error: bool, completed_at: float, payload: Any) -> dict[str, Any]:
    content = dict(getattr(active, "terminal_content", open_content(
        active.run_id or active.tool_call_id, active.started_at,
    )))
    result = _find_result(payload)
    if result:
        content.update({key: result[key] for key in (
            "stdout", "stderr", "exit_code", "duration_ms", "truncated",
        ) if key in result})
        if result.get("cancelled"):
            content["status"] = "cancelled"
        elif result.get("timed_out"):
            content["status"] = "timed_out"
        elif result.get("exit_code") not in (None, 0):
            content["status"] = "failed"
        else:
            content["status"] = "completed"
    elif is_error:
        content["status"] = "failed"
    content["completed_at"] = completed_at
    return TerminalCommandActivity.model_validate(content).model_dump(mode="json")


def event_to_delta(active: Any, event_type: str, payload: dict) -> list[dict[str, Any]]:
    content = getattr(active, "terminal_content", None)
    if content is None:
        content = open_content(active.run_id or active.tool_call_id, active.started_at)
        active.terminal_content = content
    ops = []
    if event_type == "devtools.command.started":
        content.update({
            "run_id": str(payload.get("run_id") or content["run_id"]),
            "command": str(payload.get("executable") or ""),
            "cwd": str(payload.get("cwd") or "."),
        })
        ops = [{"op": "replace", "path": f"/{key}", "value": content[key]}
               for key in ("run_id", "command", "cwd")]
    elif event_type == "devtools.command.output":
        stream = "stderr" if payload.get("stream") == "stderr" else "stdout"
        content[stream] += str(payload.get("text") or "")
        ops = [{"op": "replace", "path": f"/{stream}", "value": content[stream]}]
    elif event_type == "devtools.command.finished":
        status = (
            "cancelled" if payload.get("cancelled") else
            "timed_out" if payload.get("timed_out") else
            "completed" if payload.get("exit_code") == 0 and payload.get("success") else
            "failed"
        )
        content.update({
            "status": status, "exit_code": payload.get("exit_code"),
            "duration_ms": payload.get("duration_ms"),
            "truncated": bool(payload.get("truncated")),
        })
        ops = [{"op": "replace", "path": f"/{key}", "value": content[key]}
               for key in ("status", "exit_code", "duration_ms", "truncated")]
    if not ops:
        return []
    return [{
        "type": AGUIEventType.ACTIVITY_DELTA,
        "messageId": f"subagent:{active.tool_call_id}",
        "activityType": "terminal.command", "patch": ops, "timestamp": time.time(),
    }]


def _find_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if {"stdout", "stderr", "exit_code"} <= set(value):
            return value
        for nested in value.values():
            found = _find_result(nested)
            if found is not None:
                return found
    return None


__all__ = ["close_content", "event_to_delta", "open_content"]
