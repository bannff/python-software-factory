"""HTTP-contract tests for the side-chat routes (feature-map row 19).

Uses a throwaway FastAPI app + a REAL SideChatService wired to fake
planner/lookup/dispatch, proving the open/turn/close endpoints reach the
service and serialize its results — no gateway needed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime.side_routes import register_side_routes
from factory.mcp_utils.runtime.side_chat_service import SideChatService

LOOKUP = {"memory_stats": "deterministic", "session_archive": "operational"}


def _client() -> TestClient:
    service = SideChatService(
        planner=lambda q: [("memory_stats", {}), ("session_archive", {})],
        category_lookup=lambda: LOOKUP,
        dispatch=lambda name, args: {"tool": name},
    )
    app = FastAPI()
    register_side_routes(app, lambda: service)
    return TestClient(app)


def test_open_returns_slot_and_empty_turns():
    r = _client().post("/api/chat/slots/slot-1/side/open")
    assert r.status_code == 200
    assert r.json() == {"slot": "slot-1", "turns": []}


def test_turn_runs_read_only_and_refuses_mutation():
    client = _client()
    client.post("/api/chat/slots/s/side/open")
    r = client.post("/api/chat/slots/s/side/turn", json={"query": "stats then archive"})
    assert r.status_code == 200
    body = r.json()
    assert body["refused"] == ["session_archive"]
    # user turn + two recorded tool turns (one ran, one refused)
    assert len(body["turns"]) == 3
    assert body["turns"][0] == {"role": "user", "text": "stats then archive"}


def test_close_reports_whether_open():
    client = _client()
    client.post("/api/chat/slots/s/side/open")
    assert client.post("/api/chat/slots/s/side/close").json() == {"closed": True}
    assert client.post("/api/chat/slots/s/side/close").json() == {"closed": False}
