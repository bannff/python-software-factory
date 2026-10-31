"""Issue #106 — assistant text must open a NEW AG-UI message per message.

The Strands adapter stamps every text delta of every turn with the constant
upstream id ``"strands"`` (``adapters/strands_stream.py``).  The AG-UI client
keys its message list by ``messageId`` alone, so emitting that upstream id as
the AG-UI ``messageId`` appended each turn's answer to the first turn's
bubble.  The mapper must therefore treat the upstream id ONLY as a
change-detector and allocate a fresh ``uuid4`` ``messageId`` per message —
symmetric with ``_on_reasoning_text``.

Sibling to ``test_ag_ui_mapper_chat_stream.py`` so each file stays under the
200 LOC cap.
"""
from __future__ import annotations

from typing import Any

from factory.agent.runtime.models import (
    DoneEvent, TextDeltaEvent, ToolCallDeltaEvent, ToolResultEvent,
)
from factory.ui.runtime.ag_ui_mapper_chat import (
    AGUIStreamState, map_chat_stream_event,
)

from ._ag_ui_mapper_invariants import check_invariants


def _run(events: list[Any]) -> list[dict[str, Any]]:
    """Drive ONE run (one ``AGUIStreamState``) — mirrors the API route."""
    state = AGUIStreamState()
    out: list[dict[str, Any]] = []
    for e in events:
        out.extend(map_chat_stream_event(e, state))
    return out


def _text_messages(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Client-visible text messages: id + concatenated content."""
    msgs: dict[str, dict[str, Any]] = {}
    for evt in events:
        if evt["type"] == "TEXT_MESSAGE_START":
            msgs[evt["messageId"]] = {"id": evt["messageId"], "text": ""}
        elif evt["type"] == "TEXT_MESSAGE_CONTENT":
            msgs[evt["messageId"]]["text"] += evt["delta"]
    return list(msgs.values())


def _finished(content: str, upstream_id: str = "strands") -> list[Any]:
    return [
        TextDeltaEvent(content=content, message_id=upstream_id),
        DoneEvent(reason="stop"),
    ]


# --- the #106 regression ----------------------------------------------------


def test_two_turns_with_constant_upstream_id_get_distinct_message_ids() -> None:
    """Both runs stamp the Strands constant ``"strands"`` — avoid one bubble.

    The API builds a fresh ``AGUIStreamState`` per request, so two turns are
    two runs; the client only ever sees the concatenated event stream.
    """
    turn1 = _run(_finished("Paris"))
    turn2 = _run(_finished(" because"))
    for turn, expected in ((turn1, "Paris"), (turn2, " because")):
        check_invariants(turn)

    ids = [m["id"] for m in _text_messages(turn1 + turn2)]
    assert len(ids) == 2, f"expected 2 assistant bubbles, got {ids}"
    assert ids[0] != ids[1], "turn 2 reused turn 1's messageId"
    assert [m["text"] for m in _text_messages(turn1 + turn2)] == [
        "Paris", " because"]

def test_single_turn_with_two_upstream_ids_yields_two_messages() -> None:
    """A change of upstream id must still start a new message."""
    out = _run([
        TextDeltaEvent(content="a", message_id="m1"),
        TextDeltaEvent(content="b", message_id="m1"),
        TextDeltaEvent(content="c", message_id="m2"),
        DoneEvent(reason="stop"),
    ])
    check_invariants(out)
    msgs = _text_messages(out)
    assert [m["text"] for m in msgs] == ["ab", "c"]
    assert msgs[0]["id"] != msgs[1]["id"]
    starts = [e["messageId"] for e in out if e["type"] == "TEXT_MESSAGE_START"]
    ends = [e["messageId"] for e in out if e["type"] == "TEXT_MESSAGE_END"]
    assert starts == ends
    # The upstream ids never leak into the emitted stream.
    assert "m1" not in starts and "m2" not in starts


def test_same_upstream_id_across_tool_call_stays_one_message() -> None:
    """Interleaved tool cycle must not split the surrounding answer."""
    out = _run([
        TextDeltaEvent(content="Let me check. ", message_id="m1"),
        ToolCallDeltaEvent(tool_call_id="tc1", tool_name="kb_search"),
        ToolResultEvent(tool_call_id="tc1", payload={"hits": 1}),
        TextDeltaEvent(content="Found 1.", message_id="m1"),
        DoneEvent(reason="stop"),
    ])
    check_invariants(out)
    msgs = _text_messages(out)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "Let me check. Found 1."


def test_late_delta_for_closed_upstream_id_is_dropped() -> None:
    """Dedup semantics preserved: a closed upstream id never reopens."""
    out = _run([
        TextDeltaEvent(content="a", message_id="m1"),
        TextDeltaEvent(content="b", message_id="m2"),
        TextDeltaEvent(content="late", message_id="m1"),
        DoneEvent(reason="stop"),
    ])
    check_invariants(out)
    msgs = _text_messages(out)
    assert [m["text"] for m in msgs] == ["a", "b"]
    assert len(set(m["id"] for m in msgs)) == 2
