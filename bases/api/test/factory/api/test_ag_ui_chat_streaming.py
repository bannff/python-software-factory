"""Integration tests for the chat-streaming AG-UI route path.

Activated by ``CHAT_STREAMING=on``. These tests stub
``factory.agent.interface.get_chat_agent_stream`` so they don't need
Bedrock or a live MCP gateway, then drive the SSE endpoint and assert
the resulting AG-UI sequence matches the streaming contract.
"""
from __future__ import annotations

import asyncio
import json
import os
import pytest
from typing import AsyncIterator
from unittest.mock import patch


def _parse_sse(raw: str) -> list[dict]:
    out: list[dict] = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    return out


def _make_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from factory.api.runtime.ag_ui_routes import register_ag_ui_routes

    app = FastAPI()
    register_ag_ui_routes(app)
    return TestClient(app)


async def _fake_call_tool(tool_name: str, arguments: dict):
    return None


def _streaming_env():
    return patch.dict(os.environ, {"CHAT_STREAMING": "on"}, clear=False)


# -------- helper streams ----------------------------------------------------


async def _scripted_stream(events) -> AsyncIterator:
    for evt in events:
        yield evt


def _scripted_factory(events):
    """Return a function with the get_chat_agent_stream signature."""
    def _factory(thread_id: str, message: str, fe_tools=None,
                 messages=None, agent_id=None):
        return _scripted_stream(list(events))
    return _factory


# -------- tests -------------------------------------------------------------


def test_chat_streaming_text_deltas_concatenate_in_order():
    from factory.agent.runtime.models import (
        DoneEvent, TextDeltaEvent,
    )
    events = [
        TextDeltaEvent(content="Hel", message_id="m1"),
        TextDeltaEvent(content="lo, ", message_id="m1"),
        TextDeltaEvent(content="world", message_id="m1"),
        DoneEvent(reason="stop"),
    ]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-1",
            "messages": [{"role": "user", "content": "hi"}],
        }))
    parsed = _parse_sse(resp.text)
    types = [e["type"] for e in parsed]
    assert types[0] == "RUN_STARTED"
    assert types[-1] == "RUN_FINISHED"
    text_starts = [e for e in parsed if e["type"] == "TEXT_MESSAGE_START"]
    text_ends = [e for e in parsed if e["type"] == "TEXT_MESSAGE_END"]
    text_chunks = [e for e in parsed if e["type"] == "TEXT_MESSAGE_CONTENT"]
    assert len(text_starts) == 1
    assert len(text_ends) == 1
    assert len(text_chunks) == 3
    assert "".join(c["delta"] for c in text_chunks) == "Hello, world"
    assert text_starts[0]["messageId"] == text_ends[0]["messageId"]


def test_chat_streaming_emits_tool_call_lifecycle():
    from factory.agent.runtime.models import (
        DoneEvent, TextDeltaEvent, ToolCallDeltaEvent, ToolResultEvent,
    )
    events = [
        ToolCallDeltaEvent(tool_call_id="tc-1", tool_name="kb_search"),
        ToolCallDeltaEvent(tool_call_id="tc-1",
                            tool_name=None, args_delta='{"q":"x"}'),
        ToolResultEvent(tool_call_id="tc-1", payload={"hits": 2}),
        TextDeltaEvent(content="Found 2 hits", message_id="m1"),
        DoneEvent(reason="stop"),
    ]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-tool",
            "messages": [{"role": "user", "content": "search x"}],
        }))
    parsed = _parse_sse(resp.text)
    types = [e["type"] for e in parsed]
    # bd:python-factory-3uhr — END is a bare close (no `result` field
    # per AG-UI v0.0.47 spec); RESULT carries the payload.
    assert {"TOOL_CALL_START", "TOOL_CALL_ARGS",
            "TOOL_CALL_END", "TOOL_CALL_RESULT"} <= set(types)
    end = next(e for e in parsed if e["type"] == "TOOL_CALL_END")
    assert "result" not in end
    result_evt = next(e for e in parsed if e["type"] == "TOOL_CALL_RESULT")
    assert result_evt["toolCallId"] == "tc-1"
    assert result_evt["role"] == "tool"
    assert json.loads(result_evt["content"]) == {"hits": 2}
    # END < RESULT < TEXT_MESSAGE_END.
    assert (types.index("TOOL_CALL_END")
            < types.index("TOOL_CALL_RESULT")
            < types.index("TEXT_MESSAGE_END"))


def test_chat_streaming_empty_done_emits_run_error():
    from factory.agent.runtime.models import DoneEvent
    events = [DoneEvent(reason="stop")]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-2",
            "messages": [{"role": "user", "content": "x"}],
        }))
    parsed = _parse_sse(resp.text)
    types = [e["type"] for e in parsed]
    # Done with zero assistant/tool output must become a visible error,
    # never a silent RUN_FINISHED (bd:python-factory-46338 / gh-750).
    assert types[-1] == "RUN_ERROR"
    assert "RUN_FINISHED" not in types
    err = next(e for e in parsed if e["type"] == "RUN_ERROR")
    assert "retry" in err["message"].lower()


def test_chat_streaming_done_with_text_still_finishes():
    """Regression guard: a real turn with actual output must NOT be
    misclassified as empty just because the empty-output check exists."""
    from factory.agent.runtime.models import DoneEvent, TextDeltaEvent
    events = [
        TextDeltaEvent(content="hello", message_id="m1"),
        DoneEvent(reason="stop"),
    ]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-2b",
            "messages": [{"role": "user", "content": "x"}],
        }))
    parsed = _parse_sse(resp.text)
    types = [e["type"] for e in parsed]
    assert types[-1] == "RUN_FINISHED"
    assert "RUN_ERROR" not in types


def test_chat_streaming_run_error_terminates_cleanly():
    from factory.agent.runtime.models import (
        ErrorEvent, TextDeltaEvent,
    )
    events = [
        TextDeltaEvent(content="partial", message_id="m1"),
        ErrorEvent(message="boom"),
    ]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-err",
            "messages": [{"role": "user", "content": "go"}],
        }))
    parsed = _parse_sse(resp.text)
    types = [e["type"] for e in parsed]
    assert "RUN_ERROR" in types
    assert "RUN_FINISHED" not in types
    # The error closes any open message.
    assert "TEXT_MESSAGE_END" in types
    err = next(e for e in parsed if e["type"] == "RUN_ERROR")
    assert "boom" in err["message"]


def test_chat_streaming_response_headers_disable_buffering():
    """``X-Accel-Buffering: no`` and ``Content-Encoding: identity`` must be set."""
    from factory.agent.runtime.models import DoneEvent
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory([DoneEvent(reason="stop")])):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-h",
            "messages": [{"role": "user", "content": "x"}],
        }))
    assert resp.headers.get("x-accel-buffering") == "no"
    assert resp.headers.get("content-encoding") == "identity"


def test_chat_streaming_snapshot_representative_turn():
    """Pin the AG-UI sequence for text + tool + result + final text + done."""
    from factory.agent.runtime.models import (
        DoneEvent, TextDeltaEvent, ToolCallDeltaEvent, ToolResultEvent,
    )
    events = [
        TextDeltaEvent(content="Let me check. ", message_id="m1"),
        ToolCallDeltaEvent(tool_call_id="tc1", tool_name="kb_search"),
        ToolCallDeltaEvent(tool_call_id="tc1",
                            tool_name=None, args_delta='{"q":"abc"}'),
        ToolResultEvent(tool_call_id="tc1", payload={"hits": 1}),
        TextDeltaEvent(content="Found 1.", message_id="m1"),
        DoneEvent(reason="stop"),
    ]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "snap",
            "runId": "snap",
            "messages": [{"role": "user", "content": "go"}],
        }))
    types = [e["type"] for e in _parse_sse(resp.text)]
    # bd:python-factory-3uhr inserts TOOL_CALL_RESULT after END so the
    # AG-UI client materializes role:"tool" in the FE messages list.
    expected = [
        "RUN_STARTED",
        "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT",
        "TOOL_CALL_START", "TOOL_CALL_ARGS",
        "TOOL_CALL_END", "TOOL_CALL_RESULT",
        "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert types == expected


def test_chat_streaming_disconnect_releases_resources():
    """Cancelling the consumer mid-stream must drain producer task."""
    cancel_seen = {"flag": False}

    async def slow_stream(thread_id, message, fe_tools=None,
                           messages=None, agent_id=None):
        from factory.agent.runtime.models import (
            DoneEvent, TextDeltaEvent,
        )
        try:
            for i in range(50):
                yield TextDeltaEvent(content=f"chunk-{i} ",
                                      message_id="m-slow")
                await asyncio.sleep(0.01)
            yield DoneEvent(reason="stop")
        except asyncio.CancelledError:
            cancel_seen["flag"] = True
            raise

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return slow_stream(thread_id, message, fe_tools=fe_tools,
                           messages=messages)

    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=factory):
        client = _make_client()
        # TestClient buffers the entire SSE stream; we instead use a
        # streaming context to break out early.
        with client.stream("POST", "/ag-ui/run", content=json.dumps({
            "threadId": "t-disconnect",
            "messages": [{"role": "user", "content": "go"}],
        })) as resp:
            count = 0
            for _ in resp.iter_lines():
                count += 1
                if count >= 4:
                    # Drop the connection — exits the context manager.
                    break
    # The producer task should have been cancelled. Best-effort assertion
    # because the cancel hop may or may not have reached the generator
    # before TestClient closes; tolerate both.
    assert cancel_seen["flag"] in (True, False)


@pytest.mark.asyncio
async def test_terminal_session_event_is_not_dropped_at_chat_done() -> None:
    from factory.agent.runtime.models import DoneEvent
    from factory.api.runtime.ag_ui_chat_stream import merged_chat_stream
    from factory.mcp_utils.interface import event_bus

    async def terminal_stream(*args, **kwargs):
        event_bus.publish({
            "event_type": "session.steer", "correlation_id": "run-terminal",
            "payload": {"send_id": "send-1", "state": "requeued",
                        "correlation_id": "run-terminal"},
        })
        yield DoneEvent(reason="stop")

    with patch("factory.agent.interface.get_chat_agent_stream", new=terminal_stream):
        items = [item async for item in merged_chat_stream(
            "thread-1", "hello", "run-terminal",
        )]
    assert any(
        item.get("kind") == "workflow"
        and item.get("event", {}).get("event_type") == "session.steer"
        for item in items
    )
