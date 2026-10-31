"""Persisted Session binding is authoritative before graph/model selection."""
from __future__ import annotations

from factory.agent.runtime.adapters.session_steering import SessionSteeringMCP
from factory.agent.runtime.runtime_contracts import RuntimeInvocation


def request(**changes) -> RuntimeInvocation:
    values = {
        "invocation_id": "run", "agent_id": "frontend-agent", "prompt": "hello",
        "capability_scope_digest": "scope", "model_id": "frontend-model",
        "memory_scope": "frontend-scope", "thread_id": "thread",
        "tenant_id": "tenant", "owner_id": "owner",
    }
    values.update(changes)
    return RuntimeInvocation(**values)


def test_bind_uses_materialized_session_fields(monkeypatch) -> None:
    port = SessionSteeringMCP()
    monkeypatch.setattr(port, "_ensure_session", lambda _: {
        "session_id": "session", "agent_id": "stored-agent",
        "model": "openai-compat/local", "memory_scope": "stored-scope",
    })

    bound = port.bind(request())

    assert bound.agent_id == "stored-agent"
    assert bound.model_id == "openai-compat/local"
    assert bound.memory_scope == "stored-scope"
    assert bound.thread_id == "thread"


def test_bind_uses_default_scope_for_legacy_session(monkeypatch) -> None:
    port = SessionSteeringMCP()
    monkeypatch.setattr(port, "_ensure_session", lambda _: {
        "session_id": "session", "agent_id": "stored-agent",
        "model": "bedrock/model", "memory_scope": "",
    })
    assert port.bind(request()).memory_scope == "default"


def test_bind_without_identified_thread_preserves_request() -> None:
    port = SessionSteeringMCP()
    original = request(tenant_id=None, owner_id=None, thread_id=None)
    assert port.bind(original) is original
