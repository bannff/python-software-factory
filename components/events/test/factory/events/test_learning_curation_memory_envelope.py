"""Legacy bare Memory-get compatibility for learning curation."""
from __future__ import annotations

from typing import Any

import pytest

from factory.events.runtime.learning_handlers.curation import handle_learning_curation
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult


def _event() -> Event:
    return Event(
        id="evt-1", source="events.learning", type="memory.learning_stored",
        payload={"memory_id": "mem-1", "run_id": "run-1", "domain_class": "review"},
    )


def _memory() -> dict[str, Any]:
    return {
        "id": "mem-1", "user_id": "kiro-agent",
        "content": "Prefer precise evidence.", "memory_type": "long_term",
        "category": "fact", "metadata": {}, "relevance_score": 1.0,
        "created_at": "2026-01-01T00:00:00Z",
    }


def _invoker(memory_result: Any):
    calls: list[str] = []

    def invoke(name: str, **kwargs: Any) -> Any:
        calls.append(name)
        if name == "graph_get_entity":
            return {"found": True, "entity": {
                "id": "learning-mem-1", "type": "Learning",
                "properties": {"run_id": "run-1", "domain_class": "review"},
            }}
        if name == "memory_get":
            return memory_result
        if name == "graph_get_neighbors":
            return {"neighbors": []}
        if name == "learning_compute_reward":
            return ToolResult(data={
                "signals": [], "source_id": "llm-judge", "scalar": 0.8,
                "verdict": "rewarded", "reward_value": 80.0,
                "wallet_id": "wallet-kiro-agent", "provenance": {},
                "raw": {"scoring": {"f1": 0.8}}, "scoring": {"f1": 0.8},
            }).model_dump(mode="json")
        return {"ok": True}

    return invoke, calls


def test_curation_accepts_bare_memory_mapping() -> None:
    invoker, calls = _invoker(_memory())

    result = handle_learning_curation(_event(), invoker)

    assert result["status"] == "learning_curated"
    assert result["verdict"] == "useful"
    assert "graph_update_entity" in calls


@pytest.mark.parametrize("memory_result", [
    {"error": "memory unavailable"},
    {"id": "mem-1", "content": "fact"},
])
def test_curation_rejects_failed_or_malformed_bare_mapping(memory_result: dict[str, Any]) -> None:
    invoker, calls = _invoker(memory_result)

    result = handle_learning_curation(_event(), invoker)

    assert result == {
        "skipped": True, "reason": "memory_missing", "memory_id": "mem-1",
    }
    assert "learning_compute_reward" not in calls
