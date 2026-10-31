"""End-to-end reasoning trio tests for the chat-streaming AG-UI route.

Sibling to ``test_ag_ui_chat_streaming.py`` so the snapshot file stays
focused and each test module remains under the 200 LOC cap
(bd:python-factory-eyuj).

Pins the canonical ``REASONING_MESSAGE_START / CONTENT / END`` trio
required by CopilotKit v2's ``CopilotChatReasoningMessage`` (see
``@ag-ui/core`` 0.0.47 ``index.d.mts:1184-1187``). Until this lands
the v2 Thinking panel never lights up because the previous mapper
emitted non-canonical ``STEP_STARTED("reasoning") + CUSTOM("reasoning_text")``
events.
"""
from __future__ import annotations

import json
import os
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


async def _scripted_stream(events) -> AsyncIterator:
    for evt in events:
        yield evt


def _scripted_factory(events):
    def _factory(thread_id: str, message: str, fe_tools=None,
                 messages=None, agent_id=None):
        return _scripted_stream(list(events))
    return _factory


def test_chat_streaming_emits_reasoning_message_trio():
    """Pin the canonical AG-UI reasoning trio (bd:python-factory-eyuj).

    Two reasoning chunks plus a final assistant text → exactly one
    ``REASONING_MESSAGE_START``, two ``CONTENT`` events under the same
    ``messageId``, exactly one ``END`` for that ``messageId``, and the
    block closes before the assistant text bubble opens.
    """
    from factory.agent.runtime.models import (
        DoneEvent, ReasoningTextEvent, TextDeltaEvent,
    )
    events = [
        ReasoningTextEvent(content="planning..."),
        ReasoningTextEvent(content=" checking docs"),
        TextDeltaEvent(content="Done.", message_id="m1"),
        DoneEvent(reason="stop"),
    ]
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call_tool), \
         patch("factory.agent.interface.get_chat_agent_stream",
               new=_scripted_factory(events)):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "t-r",
            "messages": [{"role": "user", "content": "go"}],
        }))
    parsed = _parse_sse(resp.text)
    types = [e["type"] for e in parsed]
    starts = [e for e in parsed if e["type"] == "REASONING_MESSAGE_START"]
    contents = [e for e in parsed
                if e["type"] == "REASONING_MESSAGE_CONTENT"]
    ends = [e for e in parsed if e["type"] == "REASONING_MESSAGE_END"]
    assert len(starts) == 1
    assert len(contents) == 2
    assert len(ends) == 1
    msg_id = starts[0]["messageId"]
    assert all(c["messageId"] == msg_id for c in contents)
    assert ends[0]["messageId"] == msg_id
    # END before any TEXT_MESSAGE_START so the v2 Thinking panel closes
    # before the assistant bubble opens.
    assert (types.index("REASONING_MESSAGE_END")
            < types.index("TEXT_MESSAGE_START"))
    # No legacy CUSTOM("reasoning_text") events leak through.
    customs = [e for e in parsed if e["type"] == "CUSTOM"
               and e.get("name") == "reasoning_text"]
    assert customs == []
