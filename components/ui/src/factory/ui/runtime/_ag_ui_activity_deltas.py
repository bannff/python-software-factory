"""Workflow lifecycle to bounded AG-UI activity delta helpers."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from .ag_ui_activity_models import (
    NodeActivity, SubagentGraphActivity, SubagentSwarmActivity,
)
from .ag_ui_mapper import AGUIEventType

if TYPE_CHECKING:  # pragma: no cover
    from .ag_ui_mapper_activity import _ActiveRun

# Lifecycle event types that mutate ``content.nodes``.
_NODE_START_EVENTS = frozenset({"swarm.node_start", "graph.node_start"})
_NODE_STOP_EVENTS = frozenset({"swarm.node_stop", "graph.node_stop"})
_NODE_HANDOFF_EVENTS = frozenset({"swarm.handoff"})
_NODE_ERROR_EVENTS = frozenset({"graph.node_error"})

_LAUNCHED_EVENTS = frozenset({
    "swarm.launched", "graph.launched", "devtools.command.started",
})


def _ts() -> float:
    return time.time()


def _msg_id(run_id: str) -> str:
    return f"subagent:{run_id}"


def _delta(active: "_ActiveRun", ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"type": AGUIEventType.ACTIVITY_DELTA, "messageId": _msg_id(active.tool_call_id),
             "activityType": active.activity_type, "patch": ops, "timestamp": _ts()}]


def workflow_to_delta(
    active: "_ActiveRun", event_type: str, payload: dict,
) -> list[dict[str, Any]]:
    """Dispatch a workflow event_type to its delta builder."""
    if event_type in _NODE_START_EVENTS:
        return _on_node_start(active, payload)
    if event_type in _NODE_HANDOFF_EVENTS:
        return _on_handoff(active, payload)
    if event_type in _NODE_STOP_EVENTS:
        return _on_node_stop(active, payload, error=False)
    if event_type in _NODE_ERROR_EVENTS:
        return _on_node_stop(active, payload, error=True)
    return []


def _on_node_start(
    active: "_ActiveRun", payload: dict,
) -> list[dict[str, Any]]:
    node_id = str(payload.get("node_id") or "")
    if not node_id:
        return []
    started_at = float(payload.get("ts") or _ts())
    node = NodeActivity(
        node_id=node_id, status="running", started_at=started_at,
    ).model_dump(mode="json")
    idx = len(active.nodes)
    active.nodes.append(node)
    active.node_index[node_id] = idx
    return _delta(active, [
        {"op": "add", "path": f"/nodes/{idx}", "value": node},
    ])


def _on_handoff(
    active: "_ActiveRun", payload: dict,
) -> list[dict[str, Any]]:
    target = str(payload.get("to") or payload.get("node_id") or "")
    source = str(payload.get("from") or "") or None
    if not target:
        return []
    idx = active.node_index.get(target)
    if idx is None:
        # implicit start when the SDK emits handoff before node_start
        node = NodeActivity(
            node_id=target, status="running", started_at=_ts(),
            handoff_from=source,
        ).model_dump(mode="json")
        idx = len(active.nodes)
        active.nodes.append(node)
        active.node_index[target] = idx
        return _delta(active, [
            {"op": "add", "path": f"/nodes/{idx}", "value": node},
        ])
    active.nodes[idx]["handoff_from"] = source
    return _delta(active, [
        {"op": "replace",
         "path": f"/nodes/{idx}/handoff_from", "value": source},
    ])


def _on_node_stop(
    active: "_ActiveRun", payload: dict, *, error: bool,
) -> list[dict[str, Any]]:
    node_id = str(payload.get("node_id") or "")
    if not node_id:
        return []
    idx = active.node_index.get(node_id)
    if idx is None:
        return []
    stopped_at = float(payload.get("ts") or _ts())
    status = "failed" if error else "completed"
    active.nodes[idx]["status"] = status
    active.nodes[idx]["stopped_at"] = stopped_at
    ops: list[dict[str, Any]] = [
        {"op": "replace", "path": f"/nodes/{idx}/status", "value": status},
        {"op": "replace", "path": f"/nodes/{idx}/stopped_at",
         "value": stopped_at},
    ]
    if error:
        err = (str(payload.get("error") or payload.get("message")
                   or "")[:500] or None)
        active.nodes[idx]["error"] = err
        ops.append({"op": "replace", "path": f"/nodes/{idx}/error",
                    "value": err})
    return _delta(active, ops)


__all__ = ["bind_unbound_run_id", "build_close_content",
           "build_open_content", "workflow_to_delta"]


def bind_unbound_run_id(event_type: str, run_id: str, state: Any) -> list[dict[str, Any]]:
    """Link unbound run to executor envelope run_id; replay buffered events (bd:288mp)."""
    if event_type not in _LAUNCHED_EVENTS or not state.pending_unbound:
        return []
    wanted = {
        "swarm.launched": "subagent.swarm",
        "graph.launched": "subagent.graph",
        "devtools.command.started": "terminal.command",
    }[event_type]
    candidate = next(
        (p for p in state.pending_unbound if p.activity_type == wanted),
        state.pending_unbound[0],
    )
    candidate.run_id = run_id
    state.pending_unbound.remove(candidate)
    state.runs_by_run_id[run_id] = candidate
    # Replay node events buffered before swarm/graph.launched (bd:288mp).
    buffered = state.pending_node_events.pop(run_id, [])
    return [d for et, pl in buffered for d in workflow_to_delta(candidate, et, pl)]


def build_open_content(
    tool_name: str, run_id: str, started_at: float,
) -> dict[str, Any]:
    """Open snapshot content (bd:q8lle adds native spawn tool branch)."""
    if tool_name == "agent_launch_swarm":
        return SubagentSwarmActivity(
            run_id=run_id, swarm_id=run_id, status="running",
            agent_count=0, started_at=started_at,
        ).model_dump(mode="json")
    if tool_name == "agent_invoke_graph":
        return SubagentGraphActivity(
            run_id=run_id, graph_id=run_id, status="running",
            started_at=started_at,
        ).model_dump(mode="json")
    return {"run_id": run_id, "status": "running",
            "agent_id": "", "started_at": started_at}


def build_close_content(
    active: "_ActiveRun", is_error: bool,
    completed_at: float, payload: Any,
) -> dict[str, Any]:
    """Final activity content for a close snapshot (replace=True)."""
    status = "failed" if is_error else "completed"
    if active.activity_type == "subagent.single":
        c: dict[str, Any] = {
            "activityType": active.activity_type,
            "run_id": active.run_id, "status": status,
            "agent_id": "", "started_at": active.started_at,
            "completed_at": completed_at,
        }
        if is_error:
            c["error"] = str(payload)[:500]
        return c
    content: dict[str, Any] = {
        "activityType": active.activity_type,
        "run_id": active.run_id, "status": status,
        "nodes": list(active.nodes),
        "started_at": active.started_at, "completed_at": completed_at,
    }
    if active.activity_type == "subagent.swarm":
        content["swarm_id"] = active.run_id
        content["agent_count"] = len(active.nodes)
    else:
        content["graph_id"] = active.run_id
    if is_error:
        content["error"] = str(payload)[:500]
    return content
