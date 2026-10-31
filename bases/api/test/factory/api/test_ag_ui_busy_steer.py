"""Concurrent AG-UI sends become durable written steers."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime.ag_ui_routes import register_ag_ui_routes


def _events(response) -> list[dict]:
    return [json.loads(line.removeprefix("data: "))
            for line in response.text.splitlines() if line.startswith("data: ")]


def test_active_verified_send_returns_truthful_written_event(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_STREAMING", "on")
    calls: list[tuple[str, str, str]] = []

    async def verify(_tool: str, _arguments: dict):
        return {"ok": True, "data": {"ok": True, "principal": {
            "subject": "owner-1", "tenant_id": "tenant-1",
        }}}

    class Chat:
        async def steer(self, thread_id, send_id, message, **identity):
            calls.append((thread_id, send_id, message))
            assert identity["tenant_id"] == "tenant-1"
            assert identity["owner_id"] == "owner-1"
            return SimpleNamespace(
                session_id="session-1", delivery_id="delivery-1",
                send_id=send_id, revision=1,
            )

    async def forbidden_stream(*args, **kwargs):
        raise AssertionError("busy steer must not start a second Agent turn")
        yield

    app = FastAPI()
    register_ag_ui_routes(app)
    body = {
        "threadId": "thread-1", "runId": "run-steer",
        "messages": [{"id": "send-1", "role": "user", "content": "redirect now"}],
    }
    with patch("factory.api.runtime.bridge._call_tool", new=verify), \
         patch("factory.agent.interface.get_chat_agent", return_value=Chat()), \
         patch("factory.agent.interface.get_chat_agent_stream", new=forbidden_stream):
        response = TestClient(app).post(
            "/ag-ui/run", json=body,
            headers={"Authorization": "Bearer opaque"},
        )
    events = _events(response)
    assert [item["type"] for item in events] == [
        "RUN_STARTED", "CUSTOM", "RUN_FINISHED",
    ]
    assert events[1]["name"] == "session.steer"
    assert events[1]["value"] == {
        "session_id": "session-1", "delivery_id": "delivery-1",
        "send_id": "send-1", "state": "written", "revision": 1,
    }
    assert "redirect now" not in response.text
    assert calls == [("thread-1", "send-1", "redirect now")]


def test_session_transition_maps_to_custom_delivery_update() -> None:
    from factory.api.runtime.ag_ui_mapper_workflow import map_workflow_event

    events = map_workflow_event({
        "event_type": "session.steer", "source": "session",
        "payload": {
            "session_id": "session-1", "delivery_id": "delivery-1",
            "send_id": "send-1", "state": "consumed", "revision": 2,
            "correlation_id": "run-1",
        },
    })
    assert len(events) == 1
    assert events[0]["type"] == "CUSTOM"
    assert events[0]["name"] == "session.steer"
    assert events[0]["value"]["state"] == "consumed"
    assert "content" not in events[0]["value"]
