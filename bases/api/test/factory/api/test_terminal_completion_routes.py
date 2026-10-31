"""Terminal completion HTTP transport tests."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime import terminal_completion_routes as routes
from factory.terminal.runtime.models import TerminalCompletionEntry, TerminalCompletionResult


class FakeRuntime:
    def __init__(self) -> None:
        self.calls = []

    async def complete(self, tenant, principal, spec):
        self.calls.append((tenant, principal, spec))
        return TerminalCompletionResult(
            directory="/tmp", prefix=spec.token,
            entries=[TerminalCompletionEntry(name="docs", dir=True)],
        )


def _client(monkeypatch, identity=("tenant", "owner")):
    runtime = FakeRuntime()

    async def resolved(request):
        return identity

    monkeypatch.setattr(routes, "_identity", resolved)
    monkeypatch.setattr(routes, "get_runtime", lambda: runtime)
    app = FastAPI()
    routes.register_terminal_completion_routes(app)
    return TestClient(app), runtime


def test_completion_requires_identity(monkeypatch) -> None:
    client, _ = _client(monkeypatch, identity=None)
    session = "term_" + "a" * 32
    assert client.post(f"/api/terminal/sessions/{session}/complete", json={}).status_code == 401


def test_completion_validates_and_projects_result(monkeypatch) -> None:
    client, runtime = _client(monkeypatch)
    session = "term_" + "a" * 32
    response = client.post(
        f"/api/terminal/sessions/{session}/complete",
        json={"token": "do", "folders_only": True},
    )
    assert response.status_code == 200
    assert response.json()["entries"][0]["name"] == "docs"
    assert runtime.calls[0][0:2] == ("tenant", "owner")
    assert runtime.calls[0][2].session_id == session

    invalid = client.post(
        f"/api/terminal/sessions/{session}/complete",
        json={"token": "bad\n"},
    )
    assert invalid.status_code == 400
