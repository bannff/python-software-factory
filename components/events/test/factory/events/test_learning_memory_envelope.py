"""Typed Memory-store envelope regressions for learning summaries."""
from __future__ import annotations

from typing import Any

from factory.events.runtime.learning_handlers import handle_memory_learning
from factory.events.runtime.models import Event
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.mcp_utils.interface import ToolResult, set_service


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append(call["arguments"]["payload"]),
        {"ok": True},
    )[1]


def _event() -> Event:
    return Event(
        source="events.rewards", type="reward.computed",
        payload={"run_id": "run-1", "workflow_run_id": "wf-1"},
    )


def _bare_memory() -> dict[str, Any]:
    return {
        "id": "mem-1", "user_id": "kiro-agent", "content": "fact",
        "memory_type": "long_term", "category": "fact", "metadata": {},
        "relevance_score": 1.0, "created_at": "2026-01-01T00:00:00Z",
    }


def _invoker(result: Any):
    published: list[dict[str, Any]] = []
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))

    def invoke(name: str, **kwargs: Any) -> Any:
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "memory_memory_store":
            return result
        if name == "events_publish":
            published.append(kwargs["payload"])
            return {"event_id": "evt-1"}
        raise AssertionError(name)

    return invoke, published


def test_memory_learning_unwraps_stored_memory_id() -> None:
    result = ToolResult(data=MemoryStoreOutput(
        stored=True,
        memory={"id": "mem-1", "user_id": "kiro-agent", "content": "fact",
                "memory_type": "long_term", "category": "fact", "metadata": {},
                "relevance_score": 1.0, "created_at": "2026-01-01T00:00:00Z"},
    ))
    invoker, published = _invoker(result)

    out = handle_memory_learning(_event(), invoker)

    assert out["memory_id"] == "mem-1"
    assert published[0]["memory_id"] == "mem-1"


def test_memory_learning_accepts_bare_memory_mapping() -> None:
    invoker, published = _invoker(_bare_memory())

    out = handle_memory_learning(_event(), invoker)

    assert out["memory_id"] == "mem-1"
    assert published[0]["memory_id"] == "mem-1"


def test_memory_learning_accepts_bare_memory_object() -> None:
    invoker, published = _invoker(MemoryData(**_bare_memory()))

    out = handle_memory_learning(_event(), invoker)

    assert out["memory_id"] == "mem-1"
    assert published[0]["memory_id"] == "mem-1"


def test_memory_learning_rejects_malformed_bare_mapping() -> None:
    invoker, published = _invoker({"id": "mem-1", "content": "fact"})

    out = handle_memory_learning(_event(), invoker)

    assert out == {"skipped": True, "error": "memory_not_stored"}
    assert published == []


def test_memory_learning_rejects_error_store_with_memory() -> None:
    result = {
        "schema_version": "v1", "ok": True,
        "data": {"stored": True, "memory": _bare_memory(), "error": "failed"},
        "error": None, "idempotency_key": None,
    }
    invoker, published = _invoker(result)

    out = handle_memory_learning(_event(), invoker)

    assert out == {"skipped": True, "error": "failed"}
    assert published == []


def test_memory_learning_skips_normal_negative_store_outcome() -> None:
    result = ToolResult(data=MemoryStoreOutput(
        stored=False, memory=None, error="user_id required",
    ))
    invoker, published = _invoker(result)

    out = handle_memory_learning(_event(), invoker)

    assert out == {"skipped": True, "error": "user_id required"}
    assert published == []


def test_memory_learning_skips_failed_envelope() -> None:
    invoker, published = _invoker(ToolResult(
        ok=False, data=None, error="memory unavailable",
    ))

    out = handle_memory_learning(_event(), invoker)

    assert out == {"skipped": True, "error": "memory unavailable"}
    assert published == []
