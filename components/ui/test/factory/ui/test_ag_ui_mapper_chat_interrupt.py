"""bd:python-factory-6pagv — native-interrupt → AG-UI synthesis.

When ``ShellApprovalPlugin`` raises a Strands native interrupt for a
shell/python_repl call, the chat adapter surfaces an ``InterruptEvent``
and the ui mapper SYNTHESIZES the ``fe_approve_shell`` tool-call
lifecycle: ``TOOL_CALL_START`` / ``TOOL_CALL_ARGS`` / ``TOOL_CALL_END``
with NO ``TOOL_CALL_RESULT`` — the END-only choreography that makes
CopilotKit v2's ``useHumanInTheLoop`` render ``ShellApprovalCard``.

The synthesized ``toolCallId`` MUST equal the Strands ``Interrupt.id``
so the FE echoes it back for ``interruptResponse`` resume
(meta-architect ``3409d32a``). Finalize MUST NOT re-inject a RESULT.

Sibling to ``test_ag_ui_mapper_chat_stream_fe_pending.py``; stays under
the 200 LOC cap.
"""
from __future__ import annotations

import json
from typing import Any

from factory.agent.runtime.models import DoneEvent, InterruptEvent
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)


def _drive(events: list[Any]) -> tuple[AGUIStreamState, list[dict[str, Any]]]:
    state = AGUIStreamState()
    out: list[dict[str, Any]] = []
    for e in events:
        out.extend(map_chat_stream_event(e, state))
    return state, out


def test_interrupt_synthesizes_fe_approve_shell_lifecycle() -> None:
    state, out = _drive([
        InterruptEvent(interrupt_id="itr-1", tool="shell",
                       command="python --version"),
    ])
    types = [e["type"] for e in out]
    assert types == [
        "TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END",
    ], types
    start = out[0]
    assert start["toolCallName"] == "fe_approve_shell"
    # interruptId round-trips as the toolCallId on every synthesized event.
    assert all(e["toolCallId"] == "itr-1" for e in out)


def test_interrupt_args_carry_tool_and_command() -> None:
    _, out = _drive([
        InterruptEvent(interrupt_id="itr-2", tool="python_repl",
                       command="print(1)"),
    ])
    args = next(e for e in out if e["type"] == "TOOL_CALL_ARGS")
    assert json.loads(args["delta"]) == {
        "tool": "python_repl", "command": "print(1)",
    }


def test_interrupt_emits_no_result() -> None:
    """END-only — a RESULT would suppress the CopilotKit FE handler."""
    state, out = _drive([
        InterruptEvent(interrupt_id="itr-3", tool="shell", command="ls"),
    ])
    assert not any(e["type"] == "TOOL_CALL_RESULT" for e in out)
    # Marked emitted so finalize won't synthesize one.
    assert "itr-3" in state.result_emitted_tcids
    assert "itr-3" in state.seen_tool_call_ids


def test_interrupt_done_does_not_synthesize_result() -> None:
    state, out = _drive([
        InterruptEvent(interrupt_id="itr-4", tool="shell", command="whoami"),
        DoneEvent(reason="stop"),
    ])
    result_events = [e for e in out
                     if e["type"] == "TOOL_CALL_RESULT"
                     and e["toolCallId"] == "itr-4"]
    assert result_events == [], [e["type"] for e in out]
    assert state.terminated is True
    # Exactly one END for the synthesized call.
    ends = [e for e in out
            if e["type"] == "TOOL_CALL_END" and e["toolCallId"] == "itr-4"]
    assert len(ends) == 1
