"""AG-UI per-thread persona switch — ``forwardedProps.companion_x_agent_id``.

bd:python-factory-d4roe.3 (Phase 2). The FE puts the chat persona id at
``RunAgentInput.forwardedProps.companion_x_agent_id`` (via CopilotKit
``core.setProperties``); the api base parses + forwards the opaque string
to the chat adapter (transport shell — verdict ``a19ef414`` Q2). These
tests pin:

* ``parse_agent_id`` extracts / rejects per the trinary back-compat rule.
* a forwardedProps run threads ``agent_id`` to ``get_chat_agent_stream``.
* a forwardedProps-ABSENT run threads ``agent_id=None`` (byte-identical
  back-compat, verdict ``a19ef414`` Q4).
* a registry-miss persona id → clean ``RUN_ERROR`` SSE frame, NOT a 500
  or a wedged stream (verdict ``a19ef414`` Q5-ii).
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

from factory.api.runtime.ag_ui_input import parse_agent_id


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


# ── parse_agent_id unit contract ──────────────────────────────────


def test_parse_agent_id_extracts_string():
    assert parse_agent_id({"companion_x_agent_id": "grape-grower"}) == "grape-grower"


def test_parse_agent_id_absent_returns_none():
    # forwardedProps present but no selector key → None (env default).
    assert parse_agent_id({"other": "x"}) is None
    # forwardedProps absent entirely (route passes {}) → None.
    assert parse_agent_id({}) is None


def test_parse_agent_id_rejects_non_dict_and_empty():
    assert parse_agent_id(None) is None
    assert parse_agent_id("grape-grower") is None
    assert parse_agent_id({"companion_x_agent_id": ""}) is None
    assert parse_agent_id({"companion_x_agent_id": 123}) is None


# ── route threads agent_id to the chat stream ─────────────────────


def test_forwarded_props_agent_id_threaded_to_chat_stream():
    """A forwardedProps run threads the opaque id to the adapter."""
    from factory.agent.runtime.models import DoneEvent

    captured: dict[str, object] = {}

    async def _scripted(thread_id, message, fe_tools=None, messages=None,
                        agent_id=None):
        captured["agent_id"] = agent_id
        yield DoneEvent(reason="stop")

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _scripted(thread_id, message, fe_tools=fe_tools,
                         messages=messages, agent_id=agent_id)

    body = {
        "threadId": "persona-thread",
        "messages": [{"role": "user", "content": "hi"}],
        "forwardedProps": {"companion_x_agent_id": "grape-grower"},
    }
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps(body))

    assert resp.status_code == 200
    assert captured["agent_id"] == "grape-grower"


def test_forwarded_props_absent_threads_none_agent_id():
    """Back-compat (verdict a19ef414 Q4): no forwardedProps → agent_id=None
    reaches the adapter, which falls back to the env default."""
    from factory.agent.runtime.models import DoneEvent

    captured: dict[str, object] = {"agent_id": "SENTINEL"}

    async def _scripted(thread_id, message, fe_tools=None, messages=None,
                        agent_id=None):
        captured["agent_id"] = agent_id
        yield DoneEvent(reason="stop")

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _scripted(thread_id, message, fe_tools=fe_tools,
                         messages=messages, agent_id=agent_id)

    body = {
        "threadId": "plain-thread",
        "messages": [{"role": "user", "content": "hi"}],
    }
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps(body))

    assert resp.status_code == 200
    assert captured["agent_id"] is None


def test_resolve_miss_emits_clean_run_error():
    """An attacker-influenced but unregistered persona id misses the
    registry → ``resolve_agent_config`` raises ``ValueError`` →
    ``_get_or_create`` propagates → adapter yields ``ErrorEvent`` →
    the mapper emits a terminal ``RUN_ERROR`` (verdict a19ef414 Q5-ii).
    No 500, no wedged stream."""
    from factory.agent.runtime.models import ErrorEvent

    async def _scripted(thread_id, message, fe_tools=None, messages=None,
                        agent_id=None):
        # Mirror the adapter's _stream_once ValueError → ErrorEvent path.
        yield ErrorEvent(
            message=f"COMPANION_X_CHAT_AGENT_ID={agent_id!r} does not "
                    "resolve to a registered agent. Known ids: ['companion-x-default']",
        )

    def factory(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        return _scripted(thread_id, message, fe_tools=fe_tools,
                         messages=messages, agent_id=agent_id)

    body = {
        "threadId": "ghost-thread",
        "messages": [{"role": "user", "content": "hi"}],
        "forwardedProps": {"companion_x_agent_id": "ghost-persona-zzz"},
    }
    with _streaming_env(), \
         patch("factory.api.runtime.ag_ui_routes._call_tool",
               side_effect=_fake_call), \
         patch("factory.agent.interface.get_chat_agent_stream", new=factory):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=json.dumps(body))

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "RUN_ERROR" in types
    err = next(e for e in events if e["type"] == "RUN_ERROR")
    assert "ghost-persona-zzz" in err["message"]
    # Stream still terminates cleanly — RUN_STARTED present, no exception.
    assert types[0] == "RUN_STARTED"
