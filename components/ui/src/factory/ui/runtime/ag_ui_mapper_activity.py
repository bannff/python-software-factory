"""Stateful AG-UI activity mapper for synchronous and durable sub-agent tools."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ._ag_ui_activity_deltas import (
    _LAUNCHED_EVENTS, bind_unbound_run_id, build_close_content,
    build_open_content, workflow_to_delta,
)
from .ag_ui_mapper import AGUIEventType
from ._ag_ui_terminal_activity import close_content as terminal_close, event_to_delta as terminal_delta, open_content as terminal_open
from ._ag_ui_background_activity import (
    bind_background_result, map_background_workflow,
)

# MCP tool names that trigger activity snapshots (bd:q8lle adds spawn_*).
ACTIVITY_TOOL_NAMES = frozenset({
    "agent_launch_swarm", "agent_invoke_graph",
    "spawn_subagent", "spawn_swarm", "spawn_graph", "spawn_registered_graph",
    "agent_spawn_background", "devtools_run_command",
})

_TOOL_TO_ACTIVITY_TYPE: dict[str, str] = {
    "agent_launch_swarm": "subagent.swarm",
    "agent_invoke_graph": "subagent.graph",
    "spawn_subagent": "subagent.single",
    "spawn_swarm": "subagent.swarm",
    "spawn_graph": "subagent.graph",
    "spawn_registered_graph": "subagent.graph",
    "agent_spawn_background": "subagent.single",
    "devtools_run_command": "terminal.command",
}

# Spawn tools ride tool_stream directly — use tcid as run_id immediately.
_NATIVE_SPAWN_TOOLS = frozenset(
    {"spawn_subagent", "spawn_swarm", "spawn_graph", "spawn_registered_graph"}
)


def _ts() -> float:
    return time.time()


def _msg_id(run_id: str) -> str:
    """Stable activity messageId across the open / N deltas / close."""
    return f"subagent:{run_id}"


@dataclass
class _ActiveRun:
    """Per-run mutable state for snapshot-bookend bookkeeping."""

    activity_type: str
    run_id: str | None  # None until swarm.launched/graph.launched binds it
    tool_call_id: str
    tool_name: str
    started_at: float
    nodes: list[dict[str, Any]] = field(default_factory=list)
    node_index: dict[str, int] = field(default_factory=dict)


@dataclass
class AGUIActivityState:
    """Per-stream activity lookup, pending binding, and event replay state."""

    runs_by_run_id: dict[str, _ActiveRun] = field(default_factory=dict)
    runs_by_tool_call_id: dict[str, _ActiveRun] = field(default_factory=dict)
    pending_unbound: list[_ActiveRun] = field(default_factory=list)
    pending_node_events: dict[str, list[tuple[str, dict]]] = field(
        default_factory=dict
    )


def map_activity_event(
    event: dict[str, Any], state: AGUIActivityState,
) -> list[dict[str, Any]]:
    """Translate one merged-stream item to AG-UI activity events."""
    if not isinstance(event, dict):
        return []
    kind = event.get("kind")
    if kind == "chat":
        chat_event = event.get("event")
        if chat_event is None:
            return []
        et = getattr(chat_event, "type", None)
        if et == "tool_call_delta":
            return _open_snapshot(chat_event, state)
        if et == "tool_result":
            return _close_snapshot(chat_event, state)
        return []
    if kind == "workflow":
        return _on_workflow_event(event.get("event"), state)
    return []


def _open_snapshot(
    chat_event: Any, state: AGUIActivityState,
) -> list[dict[str, Any]]:
    tcid = chat_event.tool_call_id
    if tcid in state.runs_by_tool_call_id:
        return []
    tool_name = chat_event.tool_name or ""
    if tool_name not in ACTIVITY_TOOL_NAMES:
        return []
    activity_type = _TOOL_TO_ACTIVITY_TYPE[tool_name]
    started_at = _ts()
    active = _ActiveRun(activity_type=activity_type, run_id=None,
                        tool_call_id=tcid, tool_name=tool_name,
                        started_at=started_at)
    state.runs_by_tool_call_id[tcid] = active
    if tool_name in _NATIVE_SPAWN_TOOLS:
        # No launched event — bind run_id immediately.
        active.run_id = tcid
        state.runs_by_run_id[tcid] = active
    else:
        state.pending_unbound.append(active)
    content = (terminal_open(tcid, started_at)
               if activity_type == "terminal.command"
               else build_open_content(tool_name, tcid, started_at))
    if activity_type == "terminal.command":
        active.terminal_content = content
    return [{
        "type": AGUIEventType.ACTIVITY_SNAPSHOT,
        "messageId": _msg_id(tcid), "activityType": activity_type,
        "content": content, "replace": False, "timestamp": started_at,
    }]


def _close_snapshot(
    chat_event: Any, state: AGUIActivityState,
) -> list[dict[str, Any]]:
    tcid = chat_event.tool_call_id
    active = state.runs_by_tool_call_id.get(tcid)
    if active is None:
        return []
    background = bind_background_result(chat_event, active, state)
    if background is not None:
        return background
    state.runs_by_tool_call_id.pop(tcid, None)
    if active.run_id is not None:
        state.runs_by_run_id.pop(active.run_id, None)
    if active in state.pending_unbound:
        state.pending_unbound.remove(active)
    is_error = bool(getattr(chat_event, "is_error", False))
    completed_at = _ts()
    content = (terminal_close(active, is_error, completed_at,
                              getattr(chat_event, "payload", None))
               if active.activity_type == "terminal.command"
               else build_close_content(active, is_error, completed_at,
                                        getattr(chat_event, "payload", None)))
    return [{
        "type": AGUIEventType.ACTIVITY_SNAPSHOT,
        "messageId": _msg_id(tcid), "activityType": active.activity_type,
        "content": content, "replace": True, "timestamp": completed_at,
    }]


def _on_workflow_event(
    raw: Any, state: AGUIActivityState,
) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    event_type = raw.get("event_type")
    if event_type is None:
        return []
    payload = raw.get("payload") or {}
    rid = payload.get("workflow_run_id") or payload.get("run_id")
    if not rid:
        return []
    # bd-keha: bind executor envelope run_id on swarm/graph.launched.
    # Returns buffered events that arrived before launched (bd:288mp).
    replayed = bind_unbound_run_id(event_type, str(rid), state)
    active = state.runs_by_run_id.get(str(rid))
    if active is None:
        # bd:288mp — buffer node events arriving before swarm.launched.
        if event_type not in _LAUNCHED_EVENTS:
            state.pending_node_events.setdefault(str(rid), []).append(
                (event_type, payload)
            )
        return []
    background = map_background_workflow(raw, active, state)
    if background is not None:
        return background
    out: list[dict[str, Any]] = list(replayed) if replayed else []
    if active.activity_type == "terminal.command":
        out.extend(terminal_delta(active, event_type, payload))
    else:
        out.extend(workflow_to_delta(active, event_type, payload))
    return out


__all__ = [
    "ACTIVITY_TOOL_NAMES", "AGUIActivityState", "map_activity_event",
]
