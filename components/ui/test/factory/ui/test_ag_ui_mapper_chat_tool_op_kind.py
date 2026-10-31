"""opKind stamping on TOOL_CALL_START (bd:python-factory-rk4hc, Contract A).

The chat-tool mapper stamps camelCase ``opKind`` onto the TOOL_CALL_START
dict when ``ToolCallDeltaEvent.op_kind`` is present, mirroring how
``parentMessageId`` is conditionally added. Final shape:
``{type,toolCallId,toolCallName,timestamp,parentMessageId?,opKind?}``.
"""
from __future__ import annotations

from typing import Any

from factory.agent.runtime.models import ToolCallDeltaEvent
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)


def _start(event: ToolCallDeltaEvent) -> dict[str, Any]:
    state = AGUIStreamState()
    out = map_chat_stream_event(event, state)
    starts = [e for e in out if e["type"] == "TOOL_CALL_START"]
    assert len(starts) == 1
    return starts[0]


def test_op_kind_shell_stamped_as_camelcase() -> None:
    evt = _start(ToolCallDeltaEvent(
        tool_call_id="t1", tool_name="shell", op_kind="shell"))
    assert evt["opKind"] == "shell"
    assert evt["toolCallName"] == "shell"


def test_op_kind_omitted_when_none() -> None:
    evt = _start(ToolCallDeltaEvent(tool_call_id="t1", tool_name="kb_search"))
    assert "opKind" not in evt


def test_start_shape_is_canonical() -> None:
    """{type,toolCallId,toolCallName,timestamp,opKind} — no parentMessageId
    when there's no spawn parent."""
    evt = _start(ToolCallDeltaEvent(
        tool_call_id="t1", tool_name="shell", op_kind="shell"))
    assert set(evt) == {
        "type", "toolCallId", "toolCallName", "timestamp", "opKind"}


def test_op_kind_coexists_with_parent_message_id() -> None:
    evt = _start(ToolCallDeltaEvent(
        tool_call_id="t1", tool_name="shell", op_kind="shell",
        parent_tool_call_id="spawn-0"))
    assert evt["opKind"] == "shell"
    assert evt["parentMessageId"] == "spawn-0"


def test_non_shell_kinds_stamped() -> None:
    for kind in ("read", "write", "authoring"):
        evt = _start(ToolCallDeltaEvent(
            tool_call_id="t1", tool_name="x", op_kind=kind))
        assert evt["opKind"] == kind
