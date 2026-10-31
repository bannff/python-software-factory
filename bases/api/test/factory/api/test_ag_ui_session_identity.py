"""Verified AG-UI identity reaches Agent runtime context without token egress."""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.runtime.ag_ui_routes import register_ag_ui_routes
from factory.agent.runtime.models import DoneEvent, TextDeltaEvent
from factory.auth.mcp.contracts.models import VerifyAccessTokenOutput
from factory.mcp_utils.interface import make_serializable, ok


def _auth_result(*, valid: bool, tenant_id: str | None = "tenant-a") -> dict:
    principal = {"subject": "owner-a", "tenant_id": tenant_id}
    return make_serializable(ok(VerifyAccessTokenOutput(
        ok=valid, principal=principal, error=None if valid else "invalid_token",
    )))


def test_verified_identity_reaches_chat_stream(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_STREAMING", "on")
    captured: dict[str, object] = {}

    async def verify(tool_name: str, arguments: dict):
        assert tool_name == "auth_verify_access_token"
        assert arguments == {"token": "opaque-token"}
        return _auth_result(valid=True)

    async def scripted(thread_id, message, fe_tools=None, messages=None,
                       agent_id=None, model_id=None, tenant_id=None, owner_id=None):
        captured.update(
            thread_id=thread_id, model_id=model_id,
            tenant_id=tenant_id, owner_id=owner_id,
        )
        yield TextDeltaEvent(content="ok", message_id="m1")
        yield DoneEvent(reason="stop")

    app = FastAPI()
    register_ag_ui_routes(app)
    body = {
        "threadId": "thread-a", "runId": "run-a",
        "forwardedProps": {"companion_x_model": "openai-compat/local"},
        "messages": [{"role": "user", "content": "hello"}],
    }
    with patch("factory.api.runtime.bridge._call_tool", new=verify), \
         patch("factory.agent.interface.get_chat_agent_stream", new=scripted):
        response = TestClient(app).post(
            "/ag-ui/run", json=body,
            headers={"Authorization": "Bearer opaque-token"},
        )
    assert response.status_code == 200
    assert captured == {
        "thread_id": "thread-a", "model_id": "openai-compat/local",
        "tenant_id": "tenant-a", "owner_id": "owner-a",
    }
    assert "opaque-token" not in response.text


def test_incomplete_verified_identity_is_not_propagated(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_STREAMING", "on")
    captured: dict[str, object] = {}

    async def verify(_tool_name: str, _arguments: dict):
        return _auth_result(valid=True, tenant_id=None)

    async def scripted(thread_id, message, fe_tools=None, messages=None,
                       agent_id=None, **identity):
        captured.update(identity)
        yield TextDeltaEvent(content="ok", message_id="m1")
        yield DoneEvent(reason="stop")

    app = FastAPI()
    register_ag_ui_routes(app)
    with patch("factory.api.runtime.bridge._call_tool", new=verify), \
         patch("factory.agent.interface.get_chat_agent_stream", new=scripted):
        response = TestClient(app).post(
            "/ag-ui/run",
            json={"threadId": "thread-a", "messages": [
                {"role": "user", "content": "hello"},
            ]},
            headers={"Authorization": "Bearer opaque-token"},
        )
    assert response.status_code == 200
    assert captured == {}
