"""Terminal HTTP/WebSocket transport acceptance tests."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime import terminal_socket_owners, terminal_ws_routes as routes
from factory.terminal.runtime.models import TerminalSessionRef


class FakeRuntime:
    def __init__(self) -> None:
        self.session = TerminalSessionRef(
            session_id="term_" + "a" * 32, shell="/bin/zsh", cwd="/tmp",
            cols=80, rows=24, alive=True,
        )
        self.writes: list[str] = []
        self.resizes: list[tuple[int, int]] = []
        self.closed = False
        self.close_allowed = True
        self.epoch = 0
        self.disconnected: list[int] = []

    async def open_session(self, tenant, principal, spec):
        return self.session

    async def list_sessions(self, tenant, principal):
        return [] if self.closed else [self.session]

    async def close_session(self, tenant, principal, session_id):
        if not self.close_allowed:
            return False
        self.closed = True
        return True

    def list_shells(self):
        return ["/bin/zsh"]

    def connect_session(self, tenant, principal, session_id):
        self.epoch += 1
        return self.session, b"REPLAY", self.epoch

    def connection_is_current(self, tenant, principal, session_id, epoch):
        return epoch == self.epoch

    def disconnect_session(self, tenant, principal, session_id, epoch):
        if epoch != self.epoch:
            return False
        self.disconnected.append(epoch)
        return True

    async def read_bytes(self, tenant, principal, session_id, timeout):
        await asyncio.sleep(0.01)
        return b"", True

    async def write_bytes(self, tenant, principal, session_id, data):
        self.writes.append(data)

    async def resize(self, tenant, principal, session_id, cols, rows):
        self.resizes.append((cols, rows))
        self.session = self.session.model_copy(update={"cols": cols, "rows": rows})
        return self.session


def _client(monkeypatch, identity=("tenant", "owner")):
    runtime = FakeRuntime()

    async def resolved(request):
        return identity

    monkeypatch.setattr(routes, "_identity", resolved)
    monkeypatch.setattr(routes, "get_runtime", lambda: runtime)
    routes._TICKETS.clear()
    terminal_socket_owners.reset_socket_owners()
    app = FastAPI()
    routes.register_terminal_routes(app)
    return TestClient(app), runtime


def test_session_routes_require_identity(monkeypatch) -> None:
    client, _ = _client(monkeypatch, identity=None)
    assert client.post("/api/terminal/sessions", json={}).status_code == 401
    assert client.get("/api/terminal/sessions").status_code == 401
    assert client.get("/api/terminal/shells").status_code == 401


def test_session_create_list_shells_and_delete(monkeypatch) -> None:
    client, runtime = _client(monkeypatch)
    created = client.post("/api/terminal/sessions", json={})
    assert created.status_code == 200
    body = created.json()
    assert body["session"]["session_id"] == runtime.session.session_id
    assert len(body["ticket"]) >= 32
    assert client.get("/api/terminal/sessions").json()["sessions"][0]["shell"] == "/bin/zsh"
    assert client.get("/api/terminal/shells").json() == {"shells": ["/bin/zsh"]}
    deleted = client.delete(f"/api/terminal/sessions/{runtime.session.session_id}")
    assert deleted.json()["closed"] is True


def test_failed_owner_close_does_not_tear_down_socket(monkeypatch) -> None:
    client, runtime = _client(monkeypatch)
    runtime.close_allowed = False
    close = AsyncMock()
    monkeypatch.setattr(routes, "close_socket", close)
    response = client.delete(f"/api/terminal/sessions/{runtime.session.session_id}")
    assert response.status_code == 200
    assert response.json()["closed"] is False
    close.assert_not_awaited()


def test_websocket_requires_bound_ticket_and_streams_both_directions(monkeypatch) -> None:
    client, runtime = _client(monkeypatch)
    created = client.post("/api/terminal/sessions", json={}).json()
    session_id, ticket = created["session"]["session_id"], created["ticket"]

    with client.websocket_connect(
        f"/api/terminal/ws/{session_id}", subprotocols=[f"terminal.{ticket}"],
    ) as websocket:
        ready = websocket.receive_json()
        assert ready == {"type": "ready", "shell": "/bin/zsh", "cols": 80, "rows": 24}
        assert websocket.receive_bytes() == b"REPLAY"
        websocket.send_bytes(b"echo hello\n")
        websocket.send_json({"type": "resize", "cols": 120, "rows": 40})
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

    assert runtime.writes == [b"echo hello\n"]
    assert runtime.resizes == [(120, 40)]

    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect(
            f"/api/terminal/ws/{session_id}", subprotocols=["terminal.wrong"],
        ):
            pass
    assert denied.value.code == 4403


def test_new_websocket_displaces_old_without_stale_disconnect(monkeypatch) -> None:
    client, runtime = _client(monkeypatch)
    created = client.post("/api/terminal/sessions", json={}).json()
    session_id, first_ticket = created["session"]["session_id"], created["ticket"]

    with client.websocket_connect(
        f"/api/terminal/ws/{session_id}",
        subprotocols=[f"terminal.{first_ticket}"],
    ) as first:
        assert first.receive_json()["type"] == "ready"
        assert first.receive_bytes() == b"REPLAY"
        second_ticket = client.post(
            f"/api/terminal/sessions/{session_id}/attach", json={},
        ).json()["ticket"]
        with client.websocket_connect(
            f"/api/terminal/ws/{session_id}",
            subprotocols=[f"terminal.{second_ticket}"],
        ) as second:
            assert second.receive_json()["type"] == "ready"
            assert second.receive_bytes() == b"REPLAY"
            assert first.receive_json() == {"type": "error", "code": "displaced"}
            second.send_json({"type": "ping"})
            assert second.receive_json() == {"type": "pong"}
            assert runtime.disconnected == []
