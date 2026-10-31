"""Race-condition tests for the activity mapper timing fix (bd:python-factory-288mp).

Covers three scenarios:
1. Node events arrive BEFORE swarm.launched — buffered and replayed on launch.
2. Normal order (launched before node) — regression guard.
3. Multiple buffered events for same run_id — all replayed in order.
"""
from __future__ import annotations

from typing import Any

from factory.agent.runtime.models import (
    ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.runtime.ag_ui_mapper_activity import (
    AGUIActivityState, map_activity_event,
)


def _chat(ev: Any) -> dict[str, Any]:
    return {"kind": "chat", "event": ev}


def _wf(et: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "workflow", "event": {"event_type": et, "payload": payload}}


def _tcd(tcid: str, name: str) -> dict[str, Any]:
    return _chat(ToolCallDeltaEvent(tool_call_id=tcid, tool_name=name, args_delta=""))


def _launched(rid: str, kind: str = "swarm") -> dict[str, Any]:
    et = "swarm.launched" if kind == "swarm" else "graph.launched"
    return _wf(et, {"workflow_run_id": rid})


def _drive(items: list[dict[str, Any]]) -> tuple[AGUIActivityState, list[dict[str, Any]]]:
    state = AGUIActivityState()
    out: list[dict[str, Any]] = []
    for item in items:
        out.extend(map_activity_event(item, state))
    return state, out


# ---------------------------------------------------------------------------
# 1. Inverted order: node_start arrives BEFORE swarm.launched
# ---------------------------------------------------------------------------

def test_node_start_before_launched_is_replayed() -> None:
    """node_start before swarm.launched must be buffered then emitted on launch."""
    _state, out = _drive([
        _tcd("tc1", "agent_launch_swarm"),
        # node_start arrives first — launched hasn't bound run_id yet
        _wf("swarm.node_start", {"workflow_run_id": "rid1", "node_id": "scout"}),
        # launched arrives late — should replay the buffered node_start
        _launched("rid1"),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    assert len(deltas) == 1, f"Expected 1 delta from replay, got {len(deltas)}"
    assert deltas[0]["patch"][0]["op"] == "add"
    assert deltas[0]["patch"][0]["path"] == "/nodes/0"
    assert deltas[0]["patch"][0]["value"]["node_id"] == "scout"


def test_pending_node_events_cleared_after_replay() -> None:
    """pending_node_events must be empty after swarm.launched consumes the buffer."""
    state, _out = _drive([
        _tcd("tc2", "agent_launch_swarm"),
        _wf("swarm.node_start", {"workflow_run_id": "rid2", "node_id": "a"}),
        _launched("rid2"),
    ])
    assert state.pending_node_events == {}


def test_node_stop_before_launched_is_replayed() -> None:
    """node_stop buffered before launched must produce status delta on replay."""
    _state, out = _drive([
        _tcd("tc3", "agent_launch_swarm"),
        _wf("swarm.node_start", {"workflow_run_id": "rid3", "node_id": "b"}),
        _wf("swarm.node_stop", {"workflow_run_id": "rid3", "node_id": "b", "ts": 9.0}),
        _launched("rid3"),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    # node_start + node_stop both replayed
    assert len(deltas) == 2
    status_ops = [op for op in deltas[1]["patch"] if op["path"].endswith("/status")]
    assert status_ops[0]["value"] == "completed"


# ---------------------------------------------------------------------------
# 2. Normal order regression: launched arrives before node events
# ---------------------------------------------------------------------------

def test_normal_order_still_works() -> None:
    """launched before node_start must emit delta immediately (regression guard)."""
    _state, out = _drive([
        _tcd("tc4", "agent_launch_swarm"),
        _launched("tc4"),
        _wf("swarm.node_start", {"workflow_run_id": "tc4", "node_id": "x"}),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    assert len(deltas) == 1
    assert deltas[0]["patch"][0]["path"] == "/nodes/0"


def test_normal_order_no_pending_events() -> None:
    """In normal order, pending_node_events must remain empty throughout."""
    state, _out = _drive([
        _tcd("tc5", "agent_launch_swarm"),
        _launched("tc5"),
        _wf("swarm.node_start", {"workflow_run_id": "tc5", "node_id": "y"}),
    ])
    assert state.pending_node_events == {}


# ---------------------------------------------------------------------------
# 3. Multiple buffered events for the same run_id replayed in order
# ---------------------------------------------------------------------------

def test_multiple_buffered_events_replayed_in_order() -> None:
    """Three events buffered before launched must be replayed in arrival order."""
    _state, out = _drive([
        _tcd("tc6", "agent_launch_swarm"),
        _wf("swarm.node_start", {"workflow_run_id": "rid6", "node_id": "n1"}),
        _wf("swarm.node_start", {"workflow_run_id": "rid6", "node_id": "n2"}),
        _wf("swarm.node_stop",  {"workflow_run_id": "rid6", "node_id": "n1", "ts": 5.0}),
        _launched("rid6"),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    assert len(deltas) == 3, f"Expected 3 replayed deltas, got {len(deltas)}"
    # First delta: add /nodes/0 (n1 start)
    assert deltas[0]["patch"][0]["op"] == "add"
    assert deltas[0]["patch"][0]["value"]["node_id"] == "n1"
    # Second delta: add /nodes/1 (n2 start)
    assert deltas[1]["patch"][0]["op"] == "add"
    assert deltas[1]["patch"][0]["value"]["node_id"] == "n2"
    # Third delta: replace /nodes/0/status (n1 stop)
    status_ops = [op for op in deltas[2]["patch"] if op["path"].endswith("/status")]
    assert status_ops[0]["value"] == "completed"


def test_buffered_events_then_live_events_appended() -> None:
    """After replay, additional live events emitted after launched work correctly."""
    _state, out = _drive([
        _tcd("tc7", "agent_launch_swarm"),
        _wf("swarm.node_start", {"workflow_run_id": "rid7", "node_id": "a"}),
        _launched("rid7"),
        # live events after launched
        _wf("swarm.node_start", {"workflow_run_id": "rid7", "node_id": "b"}),
        _wf("swarm.node_stop",  {"workflow_run_id": "rid7", "node_id": "a", "ts": 2.0}),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    # 1 buffered replay (a start) + 2 live (b start, a stop)
    assert len(deltas) == 3
    node_ids_added = [
        d["patch"][0]["value"]["node_id"]
        for d in deltas
        if d["patch"][0]["op"] == "add"
    ]
    assert node_ids_added == ["a", "b"]


def test_close_snapshot_includes_replayed_nodes() -> None:
    """Close snapshot must reflect all nodes — including those replayed from buffer."""
    _state, out = _drive([
        _tcd("tc8", "agent_launch_swarm"),
        _wf("swarm.node_start", {"workflow_run_id": "rid8", "node_id": "n1"}),
        _launched("rid8"),
        _chat(ToolResultEvent(tool_call_id="tc8", payload={})),
    ])
    close = next(e for e in out if e.get("type") == "ACTIVITY_SNAPSHOT" and e["replace"])
    assert close["content"]["agent_count"] == 1
    assert close["content"]["nodes"][0]["node_id"] == "n1"
