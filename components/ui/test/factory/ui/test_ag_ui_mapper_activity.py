"""Pure-fn dispatch tests for the sub-agent activity mapper (bd-6zyg).

Sibling to ``test_ag_ui_mapper_activity_machine.py`` to keep each file
under the 200 LOC cap.
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
    return {"kind": "workflow", "event": {
        "event_type": et, "payload": payload,
    }}


def _tcd(tcid: str, name: str, args: str = "") -> dict[str, Any]:
    return _chat(ToolCallDeltaEvent(
        tool_call_id=tcid, tool_name=name, args_delta=args,
    ))


def _launched(rid: str, kind: str = "swarm") -> dict[str, Any]:
    et = "swarm.launched" if kind == "swarm" else "graph.launched"
    return _wf(et, {"workflow_run_id": rid})


def _drive(items: list[dict[str, Any]]) -> tuple[
    AGUIActivityState, list[dict[str, Any]],
]:
    state = AGUIActivityState()
    out: list[dict[str, Any]] = []
    for item in items:
        out.extend(map_activity_event(item, state))
    return state, out


def test_open_snapshot_for_swarm_tool() -> None:
    _state, out = _drive([_tcd("tc1", "agent_launch_swarm")])
    assert len(out) == 1
    evt = out[0]
    assert evt["type"] == "ACTIVITY_SNAPSHOT"
    assert evt["activityType"] == "subagent.swarm"
    assert evt["replace"] is False
    assert evt["messageId"] == "subagent:tc1"
    assert evt["content"]["status"] == "running"


def test_open_snapshot_for_graph_tool() -> None:
    _state, out = _drive([_tcd("tc2", "agent_invoke_graph")])
    assert out[0]["activityType"] == "subagent.graph"
    assert out[0]["content"]["graph_id"] == "tc2"


def test_no_open_for_non_allowlisted_tools() -> None:
    """fe_* + unrelated server tools must be ignored."""
    for name in ("fe_navigate_canvas", "kb_search"):
        _state, out = _drive([_tcd(f"tc-{name}", name)])
        assert out == [], f"{name} should not emit activity"


def test_subsequent_args_delta_is_idempotent() -> None:
    _state, out = _drive([
        _tcd("tc4", "agent_launch_swarm"),
        _tcd("tc4", "agent_launch_swarm", '{"agents":[]'),
    ])
    snapshots = [e for e in out if e["type"] == "ACTIVITY_SNAPSHOT"]
    assert len(snapshots) == 1


def test_node_start_emits_delta() -> None:
    _state, out = _drive([
        _tcd("tc5", "agent_launch_swarm"),
        _launched("tc5"),
        _wf("swarm.node_start", {"workflow_run_id": "tc5",
                                  "node_id": "scout", "ts": 1.0}),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    assert deltas, [e["type"] for e in out]
    last = deltas[-1]
    assert last["messageId"] == "subagent:tc5"
    assert last["patch"][0]["op"] == "add"
    assert last["patch"][0]["path"] == "/nodes/0"


def test_node_stop_emits_delta() -> None:
    _state, out = _drive([
        _tcd("tc6", "agent_invoke_graph"),
        _launched("tc6", kind="graph"),
        _wf("graph.node_start", {"workflow_run_id": "tc6",
                                  "node_id": "n1"}),
        _wf("graph.node_stop", {"workflow_run_id": "tc6",
                                 "node_id": "n1", "ts": 2.0}),
    ])
    deltas = [e for e in out if e["type"] == "ACTIVITY_DELTA"]
    assert len(deltas) == 2
    paths = [op["path"] for op in deltas[1]["patch"]]
    assert "/nodes/0/status" in paths
    assert "/nodes/0/stopped_at" in paths


def test_node_error_emits_failed_status() -> None:
    _state, out = _drive([
        _tcd("tc7", "agent_invoke_graph"),
        _launched("tc7", kind="graph"),
        _wf("graph.node_start", {"workflow_run_id": "tc7",
                                  "node_id": "n1"}),
        _wf("graph.node_error", {"workflow_run_id": "tc7",
                                  "node_id": "n1", "error": "boom"}),
    ])
    statuses = [op["value"] for op in out[-1]["patch"]
                 if op["path"].endswith("/status")]
    assert "failed" in statuses


def test_handoff_emits_delta() -> None:
    _state, out = _drive([
        _tcd("tc8", "agent_launch_swarm"),
        _launched("tc8"),
        _wf("swarm.node_start", {"workflow_run_id": "tc8",
                                  "node_id": "a"}),
        _wf("swarm.node_start", {"workflow_run_id": "tc8",
                                  "node_id": "b"}),
        _wf("swarm.handoff", {"workflow_run_id": "tc8",
                               "from": "a", "to": "b"}),
    ])
    last = out[-1]
    assert last["type"] == "ACTIVITY_DELTA"
    assert any(op["path"].endswith("/handoff_from") for op in last["patch"])


def test_close_snapshot_on_tool_result() -> None:
    _state, out = _drive([
        _tcd("tc9", "agent_launch_swarm"),
        _launched("tc9"),
        _wf("swarm.node_start", {"workflow_run_id": "tc9",
                                  "node_id": "n1"}),
        _chat(ToolResultEvent(
            tool_call_id="tc9", payload={"agents": ["x"]},
        )),
    ])
    closes = [e for e in out
              if e["type"] == "ACTIVITY_SNAPSHOT" and e["replace"] is True]
    assert len(closes) == 1
    assert closes[0]["content"]["status"] == "completed"
    assert closes[0]["content"]["agent_count"] == 1


def test_close_snapshot_failed_status_on_error() -> None:
    _state, out = _drive([
        _tcd("tcA", "agent_invoke_graph"),
        _chat(ToolResultEvent(
            tool_call_id="tcA", payload={"error": "X"}, is_error=True,
        )),
    ])
    closes = [e for e in out
              if e["type"] == "ACTIVITY_SNAPSHOT" and e["replace"] is True]
    assert closes[0]["content"]["status"] == "failed"
    assert "error" in closes[0]["content"]


def test_unrelated_tool_result_no_op() -> None:
    state, out = _drive([
        _chat(ToolResultEvent(tool_call_id="tcZ", payload={})),
    ])
    assert out == []
    assert state.runs_by_run_id == {}


def test_multi_tcid_concurrent_runs_independent() -> None:
    state, out = _drive([
        _tcd("r1", "agent_launch_swarm"),
        _tcd("r2", "agent_invoke_graph"),
        _launched("r1"),
        _launched("r2", kind="graph"),
        _wf("swarm.node_start", {"workflow_run_id": "r1",
                                  "node_id": "swarm-n"}),
        _wf("graph.node_start", {"workflow_run_id": "r2",
                                  "node_id": "graph-n"}),
        _chat(ToolResultEvent(tool_call_id="r1", payload={})),
    ])
    assert "r1" not in state.runs_by_run_id
    assert "r2" in state.runs_by_run_id
    swarm_d = [e for e in out if e["type"] == "ACTIVITY_DELTA"
               and e["activityType"] == "subagent.swarm"]
    graph_d = [e for e in out if e["type"] == "ACTIVITY_DELTA"
               and e["activityType"] == "subagent.graph"]
    assert len(swarm_d) == 1
    assert len(graph_d) == 1
