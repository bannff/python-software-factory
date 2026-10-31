"""Synthesized END+RESULT pair tests for stream finalization.

bd:python-factory-lmne — synthesize TOOL_CALL_END at finalize.
bd:python-factory-3uhr — Phase 1: pair END with TOOL_CALL_RESULT so the
AG-UI client can materialize a ``role:"tool"`` message.

Sibling to ``test_ag_ui_mapper_chat_stream.py`` so each file stays under
the 200 LOC cap.
"""
from __future__ import annotations

import json
from typing import Any

from factory.agent.runtime.models import (
    DoneEvent, ErrorEvent, ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)


def _drive(events: list[Any]) -> tuple[AGUIStreamState, list[dict[str, Any]]]:
    state = AGUIStreamState()
    out: list[dict[str, Any]] = []
    for e in events:
        out.extend(map_chat_stream_event(e, state))
    return state, out


def test_synthesize_tool_call_end_on_done() -> None:
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="t1",
                            tool_name="invoke_swarm_async"),
        DoneEvent(reason="stop"),
    ])
    ends = [e for e in out
            if e["type"] == "TOOL_CALL_END" and e["toolCallId"] == "t1"]
    results = [e for e in out
               if e["type"] == "TOOL_CALL_RESULT" and e["toolCallId"] == "t1"]
    assert len(ends) == 1
    assert len(results) == 1
    # END before RESULT.
    assert out.index(ends[0]) < out.index(results[0])
    body = json.loads(results[0]["content"])
    assert body == {"status": "incomplete", "reason": "stream_finalized"}
    assert results[0]["role"] == "tool"
    assert "t1" in state.result_emitted_tcids


def test_no_synthesize_when_result_arrived() -> None:
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="t1", tool_name="kb"),
        ToolResultEvent(tool_call_id="t1", payload={"ok": True}),
        DoneEvent(reason="stop"),
    ])
    ends = [e for e in out
            if e["type"] == "TOOL_CALL_END" and e["toolCallId"] == "t1"]
    results = [e for e in out
               if e["type"] == "TOOL_CALL_RESULT" and e["toolCallId"] == "t1"]
    assert len(ends) == 1
    assert len(results) == 1
    assert out.index(ends[0]) < out.index(results[0])
    body = json.loads(results[0]["content"])
    assert body == {"ok": True}
    assert state.result_emitted_tcids == {"t1"}


def test_synthesize_tool_call_end_on_error() -> None:
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="t1",
                            tool_name="invoke_graph_async"),
        ErrorEvent(message="boom"),
    ])
    types = [e["type"] for e in out]
    assert "TOOL_CALL_END" in types
    assert "TOOL_CALL_RESULT" in types
    assert "RUN_ERROR" in types
    # END < RESULT < RUN_ERROR.
    assert (types.index("TOOL_CALL_END")
            < types.index("TOOL_CALL_RESULT")
            < types.index("RUN_ERROR"))
    assert "t1" in state.result_emitted_tcids


def test_synthesize_multiple_unclosed_tools() -> None:
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="t1", tool_name="a"),
        ToolCallDeltaEvent(tool_call_id="t2", tool_name="b"),
        ToolCallDeltaEvent(tool_call_id="t3", tool_name="c"),
        ToolResultEvent(tool_call_id="t2", payload={"ok": True}),
        DoneEvent(reason="stop"),
    ])
    ends = [e for e in out if e["type"] == "TOOL_CALL_END"]
    results = [e for e in out if e["type"] == "TOOL_CALL_RESULT"]
    end_ids = [e["toolCallId"] for e in ends]
    result_ids = [e["toolCallId"] for e in results]
    assert sorted(end_ids) == ["t1", "t2", "t3"]
    assert sorted(result_ids) == ["t1", "t2", "t3"]
    # No duplicates.
    assert len(end_ids) == len(set(end_ids))
    assert len(result_ids) == len(set(result_ids))
    # Per tcid: END before RESULT.
    for tcid in ("t1", "t2", "t3"):
        end_idx = next(i for i, e in enumerate(out)
                       if e["type"] == "TOOL_CALL_END"
                       and e["toolCallId"] == tcid)
        res_idx = next(i for i, e in enumerate(out)
                       if e["type"] == "TOOL_CALL_RESULT"
                       and e["toolCallId"] == tcid)
        assert end_idx < res_idx, f"{tcid}: END must come before RESULT"
    assert state.result_emitted_tcids == {"t1", "t2", "t3"}


def test_uuid_messageid_distinct_per_result() -> None:
    """Each TOOL_CALL_RESULT MUST have a fresh UUID4 messageId."""
    _, out = _drive([
        ToolCallDeltaEvent(tool_call_id="t1", tool_name="a"),
        ToolResultEvent(tool_call_id="t1", payload={"ok": 1}),
        ToolCallDeltaEvent(tool_call_id="t2", tool_name="b"),
        ToolResultEvent(tool_call_id="t2", payload={"ok": 2}),
        DoneEvent(reason="stop"),
    ])
    results = [e for e in out if e["type"] == "TOOL_CALL_RESULT"]
    assert len(results) == 2
    mids = [r["messageId"] for r in results]
    assert len(set(mids)) == 2, "messageIds must be distinct"
    # UUID4 string format check (8-4-4-4-12).
    for mid in mids:
        parts = mid.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]
