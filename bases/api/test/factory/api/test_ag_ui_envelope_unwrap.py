"""Stream-mapper extraction tests: envelope in, prose out.

Regression coverage for the Companion-X chat verbiage bug: the legacy
``agent_reason`` path used to ``str()`` the whole typed ``ToolResult``
envelope into the assistant ``TEXT_MESSAGE_CONTENT`` delta, so users saw
raw Python reprs like ``{'schema_version': 'v1', 'ok': False, ...}``
instead of prose (both on success AND on ``tool_execution_failed``).
"""
from __future__ import annotations

import json

import pytest

from factory.api.runtime.ag_ui_helpers import (
    TOOL_FALLBACK_TEXT,
    extract_ag_ui_events,
    unwrap_agent_output,
)


def _deltas(events: list[dict]) -> list[str]:
    return [e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]


def _types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


def test_success_envelope_unwraps_to_prose_delta():
    """The nested chat_agent envelope (data.result.output) becomes prose."""
    envelope = {
        "schema_version": "v1",
        "ok": True,
        "data": {"result": {
            "workflow_type": "chat_agent",
            "status": "completed",
            "output": "Yes, I'm here! 👋",
        }},
        "error": None,
        "idempotency_key": None,
    }
    events = extract_ag_ui_events(envelope, "t1")
    assert _deltas(events) == ["Yes, I'm here! 👋"]
    assert "schema_version" not in "".join(_deltas(events))
    assert _types(events) == [
        "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END",
    ]


def test_failure_envelope_yields_prose_fallback_never_raw_repr():
    """A tool_execution_failed envelope must never surface as chat text."""
    envelope = {
        "schema_version": "v1",
        "ok": False,
        "data": None,
        "error": "tool_execution_failed",
        "idempotency_key": None,
    }
    events = extract_ag_ui_events(envelope, "t1")
    assert len(_deltas(events)) == 1
    delta = _deltas(events)[0]
    assert delta == TOOL_FALLBACK_TEXT
    for raw in ("schema_version", "tool_execution_failed", "'ok'", "ok"):
        assert raw not in delta


def test_flat_text_result_still_maps_directly():
    assert extract_ag_ui_events({"text": "plain text"}, "t1") and _deltas(
        extract_ag_ui_events({"text": "plain text"}, "t1"),
    ) == ["plain text"]


def test_flat_output_result_maps_directly():
    assert _deltas(extract_ag_ui_events({"output": "hi"}, "t1")) == ["hi"]


def test_data_output_shape_unwraps():
    envelope = {"ok": True, "data": {"output": "direct data output"}}
    assert _deltas(extract_ag_ui_events(envelope, "t1")) == [
        "direct data output",
    ]


def test_empty_result_yields_no_events():
    assert extract_ag_ui_events({}, "t1") == []
    assert extract_ag_ui_events(None, "t1") == []


def test_plain_string_result_maps_directly():
    assert _deltas(extract_ag_ui_events("just text", "t1")) == ["just text"]


def test_unwrap_agent_output_failure_envelope_is_none():
    envelope = {"schema_version": "v1", "ok": False, "data": None,
                "error": "tool_execution_failed", "idempotency_key": None}
    assert unwrap_agent_output(envelope) is None


def test_unwrap_agent_output_success_shapes():
    assert unwrap_agent_output("s") == "s"
    assert unwrap_agent_output({"text": "a"}) == "a"
    assert unwrap_agent_output({"output": "b"}) == "b"
    assert unwrap_agent_output({
        "ok": True, "data": {"result": {"output": "c"}},
    }) == "c"
    assert unwrap_agent_output({
        "ok": True, "data": {"output": "d"},
    }) == "d"
    assert unwrap_agent_output({"ok": True, "data": {}}) is None


def test_deltas_are_json_serializable():
    envelope = {"ok": True, "data": {"result": {"output": "x"}}}
    for evt in extract_ag_ui_events(envelope, "t1"):
        json.dumps(evt)


def test_extract_user_message_collapses_content_blocks():
    """AG-UI clients send content as block lists; task must be a str."""
    from factory.api.runtime.ag_ui_helpers import extract_user_message
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "take me to the metrics page"},
    ]}]
    assert extract_user_message(messages) == "take me to the metrics page"


def test_extract_user_message_concatenates_multiple_text_blocks():
    from factory.api.runtime.ag_ui_helpers import extract_user_message
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "hello "},
        {"type": "text", "text": "world"},
    ]}]
    assert extract_user_message(messages) == "hello world"


def test_extract_user_message_passthrough_shapes():
    from factory.api.runtime.ag_ui_helpers import extract_user_message
    assert extract_user_message(
        [{"role": "user", "content": "plain"}],
    ) == "plain"
    assert extract_user_message([]) == ""
    assert extract_user_message([{"role": "assistant", "content": "x"}]) == ""
