"""Integration tests for AG-UI ``RunAgentInput.tools[]`` + ``context[]``.

bd-115z extends the AG-UI body with FE-side tool registrations
(forwarded to the chat adapter) and canvas-context bullets (prepended
to the user message). Carved out of ``test_ag_ui_endpoint.py`` to keep
both files under the 200-LOC budget.
"""
from __future__ import annotations

import json
import os
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


def _streaming_env():
    return patch.dict(os.environ, {"CHAT_STREAMING": "on"}, clear=False)


async def _fake_call(tool_name, arguments):
    return None


def test_fe_tools_validated_and_threaded_to_chat_stream():
    """Valid tools[] body — parsed, forwarded as ``fe_tools``."""
    from factory.agent.runtime.models import DoneEvent, FrontendToolSpec

    captured: dict[str, object] = {}

    async def _scripted(thread_id, message, fe_tools=None, messages=None,
                        agent_id=None):
        captured["thread_id"] = thread_id
        captured["message"] = message
        captured["fe_tools"] = fe_tools
        captured["messages"] = messages
        yield DoneEvent(reason="stop")

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _scripted(thread_id, message, fe_tools=fe_tools,
                         messages=messages, agent_id=agent_id)

    body = {
        "threadId": "fe-tools-thread",
        "messages": [{"role": "user", "content": "switch view"}],
        "tools": [{
            "name": "fe_navigate_canvas",
            "description": "Switch the canvas to a different view.",
            "parameters": {
                "type": "object",
                "properties": {"view": {"type": "string"}},
                "required": ["view"],
            },
        }],
    }
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps(body))

    assert resp.status_code == 200
    fe_tools = captured["fe_tools"]
    assert isinstance(fe_tools, list) and len(fe_tools) == 1
    spec = fe_tools[0]
    assert isinstance(spec, FrontendToolSpec)
    assert spec.name == "fe_navigate_canvas"
    assert spec.parameters["properties"]["view"]["type"] == "string"
    assert captured["messages"] == body["messages"]


def test_invalid_fe_tool_emits_run_error_and_does_not_call_chat():
    """Malformed tools[] entry — RUN_ERROR, no chat stream invoked."""
    called: dict[str, bool] = {"chat": False}

    async def _never(thread_id, message, fe_tools=None, messages=None,
                     agent_id=None):
        called["chat"] = True
        yield  # pragma: no cover

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _never(thread_id, message, fe_tools=fe_tools,
                      messages=messages)

    body = {
        "threadId": "bad-tools",
        "messages": [{"role": "user", "content": "x"}],
        "tools": [{"description": "no name"}],  # missing required `name`
    }
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps(body))

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "RUN_ERROR" in types
    err = next(e for e in events if e["type"] == "RUN_ERROR")
    assert "tools[0]" in err["message"]
    assert called["chat"] is False


def test_context_items_prepended_to_user_message():
    """RunAgentInput.context[] becomes a labelled prefix on the prompt."""
    from factory.agent.runtime.models import DoneEvent

    captured: dict[str, str] = {}

    async def _scripted(thread_id, message, fe_tools=None, messages=None,
                        agent_id=None):
        captured["message"] = message
        yield DoneEvent(reason="stop")

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _scripted(thread_id, message, fe_tools=fe_tools,
                         messages=messages)

    body = {
        "threadId": "ctx-thread",
        "messages": [{"role": "user", "content": "what view am I on?"}],
        "context": [{
            "description": "Companion-X canvas state",
            "value": {"activeView": "graph"},
        }],
    }
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps(body))

    assert resp.status_code == 200
    msg = captured["message"]
    assert "Canvas context" in msg
    assert "activeView" in msg and "graph" in msg
    assert "what view am I on?" in msg


def test_no_tools_no_context_passes_through():
    """Backwards-compat: empty body → fe_tools=[] forwarded."""
    from factory.agent.runtime.models import DoneEvent

    captured: dict[str, object] = {}

    async def _scripted(thread_id, message, fe_tools=None, messages=None,
                        agent_id=None):
        captured["fe_tools"] = fe_tools
        captured["message"] = message
        yield DoneEvent(reason="stop")

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _scripted(thread_id, message, fe_tools=fe_tools,
                         messages=messages)

    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps({
            "threadId": "plain",
            "messages": [{"role": "user", "content": "hi"}],
        }))

    assert resp.status_code == 200
    assert captured["fe_tools"] in ([], None)
    assert captured["message"] == "hi"
