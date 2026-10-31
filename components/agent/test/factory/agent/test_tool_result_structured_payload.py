"""Tool-result → AG-UI payload unwrapping in ``message_events``.

Regression for the "nothing paints" bug (issue: canvas paint regression):
``invoke_capability`` returns ``asdict(CapabilityResult)`` — the MCP
``CallToolResult`` shape ``{content: [...], structured_content: {...}}``.
LangGraph stringifies that into the ``ToolMessage``, and the AG-UI
mapper ``json.dumps``-ed it back, so the frontend carrier detectors
(``detectCarrier`` in ``tool-renderers.tsx``) received a text block with
an escaped envelope instead of structured JSON — carriers #1 (A2UI) and
#5 (mcp-ui) never fired.

Contract under test: ``message_events`` unwraps MCP structured content
so ``ToolResultEvent.payload`` is the envelope dict itself; plain
non-envelope results pass through unchanged.
"""
import json

import pytest
pytest.importorskip("langchain")
from langchain_core.messages import ToolMessage

from factory.agent.runtime.adapters.langchain_stream import message_events

_PAINT_ENVELOPE = {
    "schema_version": "v1",
    "ok": True,
    "_a2ui_canvas": {
        "payload": {
            "components": [
                {"id": "t1", "type": "Text", "props": {"text": "Daniel"}},
            ],
        },
    },
}


def _capability_result_dict() -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(_PAINT_ENVELOPE)}],
        "structured_content": _PAINT_ENVELOPE,
        "is_error": False,
    }


def test_stringified_capability_result_unwraps_structured_content() -> None:
    """LangGraph's real wire shape: ``msg_content_output`` json.dumps the
    ``CapabilityResult`` asdict. The payload must be the envelope dict,
    not an escaped string inside a text block."""
    message = ToolMessage(
        content=json.dumps(_capability_result_dict()),
        tool_call_id="call_1", name="ui_paint_canvas",
    )
    events = message_events(message)
    assert len(events) == 1
    kind, payload = events[0]
    assert kind == "tool_result"
    assert payload["tool_call_id"] == "call_1"
    assert payload["payload"] == _PAINT_ENVELOPE
    assert payload["is_error"] is False


def test_calltoolresult_text_block_without_structured_content_recovers() -> None:
    """A ``CallToolResult.content`` passthrough (no ``structured_content``)
    still recovers the envelope from the single text block."""
    message = ToolMessage(
        content=json.dumps({
            "content": [{"type": "text", "text": json.dumps(_PAINT_ENVELOPE)}],
        }),
        tool_call_id="call_2", name="ui_paint_canvas",
    )
    events = message_events(message)
    assert events[0][1]["payload"] == _PAINT_ENVELOPE


def test_content_block_list_with_single_json_text_block_recovers() -> None:
    """CallToolResult.content kept as a list of content blocks."""
    message = ToolMessage(
        content=[{"type": "text", "text": json.dumps(_PAINT_ENVELOPE)}],
        tool_call_id="call_3", name="ui_paint_canvas",
    )
    events = message_events(message)
    assert events[0][1]["payload"] == _PAINT_ENVELOPE


def test_plain_string_result_passes_through() -> None:
    message = ToolMessage(
        content="plain text result", tool_call_id="call_4", name="kb_search",
    )
    events = message_events(message)
    assert events[0][1]["payload"] == "plain text result"


def test_non_envelope_dict_result_passes_through() -> None:
    result = {"hits": [{"content": "row"}]}
    message = ToolMessage(
        content=json.dumps(result), tool_call_id="call_5", name="kb_search",
    )
    events = message_events(message)
    assert events[0][1]["payload"] == result


def test_non_json_string_result_passes_through() -> None:
    message = ToolMessage(
        content="{'not': 'json'}", tool_call_id="call_6", name="local_tool",
    )
    events = message_events(message)
    assert events[0][1]["payload"] == "{'not': 'json'}"


def test_multi_block_content_list_passes_through() -> None:
    blocks = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    message = ToolMessage(content=blocks, tool_call_id="call_7", name="x")
    events = message_events(message)
    assert events[0][1]["payload"] == blocks


def test_a2ui_envelope_survives_to_mapper_result_content() -> None:
    """End of the contract: the AG-UI mapper's TOOL_CALL_RESULT content
    parses to the envelope with the ``_a2ui_canvas`` sentinel at top
    level — the shape ``detectCarrier`` needs to fire carrier #1."""
    from factory.agent.runtime.models import ToolResultEvent
    from factory.ui.runtime.ag_ui_mapper_chat import (
        AGUIStreamState, map_chat_stream_event,
    )

    message = ToolMessage(
        content=json.dumps(_capability_result_dict()),
        tool_call_id="call_8", name="ui_paint_canvas",
    )
    _, payload = message_events(message)[0]
    event = ToolResultEvent(**{**payload, "type": "tool_result"})
    state = AGUIStreamState()
    state.seen_tool_call_ids.add("call_8")
    ag_ui_events = map_chat_stream_event(event, state)
    result = [e for e in ag_ui_events if e["type"] == "TOOL_CALL_RESULT"]
    assert result, ag_ui_events
    parsed = json.loads(result[0]["content"])
    assert isinstance(parsed, dict) and "_a2ui_canvas" in parsed
    assert parsed["_a2ui_canvas"]["payload"]["components"][0]["props"][
        "text"] == "Daniel"
