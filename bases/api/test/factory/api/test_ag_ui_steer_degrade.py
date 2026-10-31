"""#86: a busy-steer offer failure must degrade the run, not 500 it."""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime.ag_ui_routes import register_ag_ui_routes


def _events(response) -> list[dict]:
    return [json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines() if line.startswith("data: ")]


def test_steer_failure_degrades_run_without_500(monkeypatch, caplog) -> None:
    """Steer that cannot be persisted: log the real cause, no session.steer
    event, and the message runs as a fresh turn (the route's idle-thread
    semantics). The old behavior re-raised before the first SSE byte -> 500."""
    monkeypatch.setenv("CHAT_STREAMING", "on")
    stream_calls: list[str] = []

    async def verify(_tool: str, _arguments: dict):
        return {"ok": True, "data": {"ok": True, "principal": {
            "subject": "owner-1", "tenant_id": "tenant-1",
        }}}

    class Chat:
        async def steer(self, thread_id, send_id, message, **identity):
            raise RuntimeError("session registration missing")

    async def fresh_turn_stream(_thread_id, _user_message, *args, **kwargs):
        from factory.agent.runtime.models import DoneEvent, TextDeltaEvent
        stream_calls.append(_thread_id)
        yield TextDeltaEvent(message_id="m1", content="ok")
        yield DoneEvent()

    app = FastAPI()
    register_ag_ui_routes(app)
    body = {
        "threadId": "thread-1", "runId": "run-steer-fail",
        "messages": [{"id": "send-1", "role": "user", "content": "redirect now"}],
    }
    with patch("factory.api.runtime.bridge._call_tool", new=verify), \
         patch("factory.agent.interface.get_chat_agent", return_value=Chat()), \
         patch("factory.agent.interface.get_chat_agent_stream", new=fresh_turn_stream), \
         caplog.at_level(logging.ERROR, logger="factory.api.runtime.ag_ui_steering"):
        response = TestClient(app, raise_server_exceptions=False).post(
            "/ag-ui/run", json=body,
            headers={"Authorization": "Bearer opaque"},
        )
    assert response.status_code == 200
    events = _events(response)
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"
    assert all(item.get("name") != "session.steer" for item in events)
    assert any(item["type"] == "TEXT_MESSAGE_CONTENT" for item in events)
    assert stream_calls == ["thread-1"]  # fresh-turn fallback, not a 500
    assert any(
        "busy steer offer failed" in record.getMessage() and record.exc_info
        for record in caplog.records
    )
