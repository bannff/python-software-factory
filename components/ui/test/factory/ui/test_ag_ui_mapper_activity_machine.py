"""``RuleBasedStateMachine`` driving the activity mapper (bd-6zyg).

Hypothesis stateful exploration of interleaved tool_call_delta + node
lifecycle + tool_result. Invariants checked after every rule:
  (a) open-snapshot precedes any delta for a given messageId;
  (b) close-snapshot has ``replace=True``;
  (c) state after open + N deltas equals state after close-replace
      (the close snapshot's content reflects the accumulated delta
      mutations).
"""
from __future__ import annotations

from typing import Any

from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, rule,
)

from factory.agent.runtime.models import (
    ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.runtime.ag_ui_mapper_activity import (
    AGUIActivityState, map_activity_event,
)

from ._ag_ui_mapper_invariants import check_invariants


_TOOLS = ("agent_launch_swarm", "agent_invoke_graph")
_RUN_IDS = ("r-alpha", "r-beta")
_NODES = ("n1", "n2", "n3")


def _wf(et: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "workflow",
            "event": {"event_type": et, "payload": payload}}


class _ActivityMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.state = AGUIActivityState()
        self.events: list[dict[str, Any]] = []
        # Tool-call -> activityType so we can replay invariant pairing.
        self._open_tcids: dict[str, str] = {}
        self._closed_tcids: set[str] = set()

    @initialize()
    def _setup(self) -> None:
        self.state = AGUIActivityState()
        self.events = []
        self._open_tcids = {}
        self._closed_tcids = set()

    @rule(tcid=st.sampled_from(_RUN_IDS),
          tool=st.sampled_from(_TOOLS))
    def open_run(self, tcid: str, tool: str) -> None:
        if tcid in self._open_tcids or tcid in self._closed_tcids:
            return
        self._open_tcids[tcid] = (
            "subagent.swarm"
            if tool == "agent_launch_swarm" else "subagent.graph")
        self.events.extend(map_activity_event({
            "kind": "chat",
            "event": ToolCallDeltaEvent(tool_call_id=tcid, tool_name=tool),
        }, self.state))

    @rule(tcid=st.sampled_from(_RUN_IDS),
          node=st.sampled_from(_NODES),
          which=st.sampled_from(["start", "stop", "handoff", "error"]))
    def node_event(self, tcid: str, node: str, which: str) -> None:
        if tcid not in self._open_tcids:
            return
        et_map = {
            "start": "swarm.node_start", "stop": "swarm.node_stop",
            "handoff": "swarm.handoff", "error": "graph.node_error",
        }
        payload: dict[str, Any] = {"workflow_run_id": tcid,
                                    "node_id": node}
        if which == "handoff":
            payload["from"] = "src"
            payload["to"] = node
        if which == "error":
            payload["error"] = "boom"
        self.events.extend(map_activity_event(
            _wf(et_map[which], payload), self.state,
        ))

    @rule(tcid=st.sampled_from(_RUN_IDS),
          err=st.booleans())
    def close_run(self, tcid: str, err: bool) -> None:
        if tcid not in self._open_tcids:
            return
        self._open_tcids.pop(tcid)
        self._closed_tcids.add(tcid)
        self.events.extend(map_activity_event({
            "kind": "chat",
            "event": ToolResultEvent(
                tool_call_id=tcid, payload={"x": 1}, is_error=err,
            ),
        }, self.state))

    @invariant()
    def invariants_hold(self) -> None:
        check_invariants(self.events, require_closure=False)

    @invariant()
    def open_close_state_consistency(self) -> None:
        # After close, state must drop the run from BOTH maps; while
        # open, the run must still be tracked by tcid (delta target).
        # bd-keha: open runs are bound to envelope ``run_id`` lazily on
        # ``swarm.launched`` / ``graph.launched``; the state-machine
        # rules don't drive launched events, so ``runs_by_run_id`` is
        # not asserted here. ``runs_by_tool_call_id`` is the canonical
        # open-run track.
        for tcid in self._closed_tcids:
            assert tcid not in self.state.runs_by_tool_call_id, (
                f"closed run {tcid} still tracked by tcid")
        for tcid in self._open_tcids:
            assert tcid in self.state.runs_by_tool_call_id, (
                f"open run {tcid} not tracked")

    @invariant()
    def close_snapshots_have_replace_true(self) -> None:
        # bd-6zyg: every ACTIVITY_SNAPSHOT in `_closed_tcids` namespace
        # MUST be replace=True; the open one is replace=False.
        seen_open: dict[str, bool] = {}
        for evt in self.events:
            if evt["type"] != "ACTIVITY_SNAPSHOT":
                continue
            mid = evt["messageId"]
            if mid not in seen_open:
                seen_open[mid] = True
                assert evt["replace"] is False, (
                    f"first snapshot for {mid} must be replace=False")
            else:
                assert evt["replace"] is True, (
                    f"second snapshot for {mid} must be replace=True")


TestActivityMachine = _ActivityMachine.TestCase
TestActivityMachine.settings = settings(
    max_examples=50, deadline=None,
    suppress_health_check=[HealthCheck.too_slow,
                            HealthCheck.filter_too_much],
)
