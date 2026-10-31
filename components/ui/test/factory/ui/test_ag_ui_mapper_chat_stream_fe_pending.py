"""bd-ioyz — FE-tool deferred-sentinel branch in ``_on_tool_result``.

When the chat adapter's ``_StubAgentTool`` yields a deferred sentinel
result (``{"_frontend_pending": True, "name": ..., "args": ...}``),
the AG-UI mapper MUST emit ``TOOL_CALL_END`` only — no
``TOOL_CALL_RESULT`` — so CopilotKit v2's ``useFrontendTool``
dispatcher fires the FE handler. Finalize MUST NOT re-inject a
synthesized RESULT for that tcid (the sentinel marks it
``result_emitted_tcids``).

Sibling to ``test_ag_ui_mapper_chat_stream_synth.py`` so each file
stays under the 200 LOC cap.

Memories: ``a807368d`` (meta-architect), ``0d78bcac`` (strands-expert).
"""
from __future__ import annotations

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


def _fe_pending_payload(name: str = "fe_navigate_canvas",
                         args: dict[str, Any] | None = None) -> dict:
    """The exact payload ``_StubAgentTool.stream`` yields for FE tools."""
    return {
        "_frontend_pending": True,
        "name": name,
        "args": dict(args or {"view": "graph"}),
    }


# --- happy path -------------------------------------------------------------


def test_fe_pending_emits_tool_call_end_only_no_result() -> None:
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="tc-fe1",
                            tool_name="fe_navigate_canvas"),
        ToolResultEvent(tool_call_id="tc-fe1",
                         payload=_fe_pending_payload()),
    ])
    types = [e["type"] for e in out]
    # Exactly one TOOL_CALL_END (paired with the prior TOOL_CALL_START).
    end_events = [e for e in out
                   if e["type"] == "TOOL_CALL_END"
                   and e["toolCallId"] == "tc-fe1"]
    result_events = [e for e in out
                      if e["type"] == "TOOL_CALL_RESULT"
                      and e["toolCallId"] == "tc-fe1"]
    assert len(end_events) == 1, types
    assert len(result_events) == 0, (
        f"FE-pending sentinel must NOT emit TOOL_CALL_RESULT: {types}"
    )
    # Marked as result-emitted so finalize doesn't re-synthesize.
    assert "tc-fe1" in state.result_emitted_tcids


def test_fe_pending_done_does_not_synthesize_result() -> None:
    """After fe-pending tool_result, ``done`` MUST NOT add a RESULT.

    The sentinel branch added the tcid to ``result_emitted_tcids``,
    so ``_synth_unclosed_tool_ends`` should treat it as already
    closed.
    """
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="tc-fe2",
                            tool_name="fe_navigate_canvas"),
        ToolResultEvent(tool_call_id="tc-fe2",
                         payload=_fe_pending_payload(
                             args={"view": "findings"})),
        DoneEvent(reason="stop"),
    ])
    end_events = [e for e in out
                   if e["type"] == "TOOL_CALL_END"
                   and e["toolCallId"] == "tc-fe2"]
    result_events = [e for e in out
                      if e["type"] == "TOOL_CALL_RESULT"
                      and e["toolCallId"] == "tc-fe2"]
    assert len(end_events) == 1, [e["type"] for e in out]
    assert len(result_events) == 0, (
        f"finalize must NOT re-inject RESULT for FE tcid: "
        f"{[e['type'] for e in out]}"
    )
    assert state.terminated is True


def test_fe_pending_error_does_not_synthesize_result() -> None:
    """Error finalize path: same skip semantics as ``done``."""
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="tc-fe3", tool_name="fe_x"),
        ToolResultEvent(tool_call_id="tc-fe3",
                         payload=_fe_pending_payload()),
        ErrorEvent(message="boom"),
    ])
    result_events = [e for e in out
                      if e["type"] == "TOOL_CALL_RESULT"
                      and e["toolCallId"] == "tc-fe3"]
    assert len(result_events) == 0, [e["type"] for e in out]
    assert any(e["type"] == "RUN_ERROR" for e in out)


# --- non-fe path is byte-identical -----------------------------------------


def test_non_fe_path_unchanged_emits_end_then_result() -> None:
    """Server-side tool (no sentinel) keeps the canonical END+RESULT."""
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="tc-srv", tool_name="kb_search"),
        ToolResultEvent(tool_call_id="tc-srv", payload={"hits": 3}),
    ])
    types = [e["type"] for e in out]
    # END before RESULT, both present.
    assert types.count("TOOL_CALL_END") == 1
    assert types.count("TOOL_CALL_RESULT") == 1
    end_idx = types.index("TOOL_CALL_END")
    res_idx = types.index("TOOL_CALL_RESULT")
    assert end_idx < res_idx
    result_evt = out[res_idx]
    import json as _j
    assert _j.loads(result_evt["content"]) == {"hits": 3}
    assert "tc-srv" in state.result_emitted_tcids


def test_fe_pending_payload_with_extra_keys_still_skips_result() -> None:
    """Detection keys on ``_frontend_pending`` only, ignores extras."""
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="tc-fe4", tool_name="fe_z"),
        ToolResultEvent(tool_call_id="tc-fe4", payload={
            "_frontend_pending": True, "name": "fe_z", "args": {},
            "extra_metadata": "ignored",
        }),
    ])
    result_events = [e for e in out if e["type"] == "TOOL_CALL_RESULT"]
    assert len(result_events) == 0
    assert "tc-fe4" in state.result_emitted_tcids


def test_fe_pending_falsy_flag_takes_normal_path() -> None:
    """Defensive: ``_frontend_pending: False`` MUST hit the normal path."""
    state, out = _drive([
        ToolCallDeltaEvent(tool_call_id="tc-srv2", tool_name="srv"),
        ToolResultEvent(tool_call_id="tc-srv2", payload={
            "_frontend_pending": False, "ok": True,
        }),
    ])
    types = [e["type"] for e in out]
    assert "TOOL_CALL_RESULT" in types
    assert "TOOL_CALL_END" in types
