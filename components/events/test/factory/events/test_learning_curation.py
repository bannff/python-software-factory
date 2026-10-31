"""Tests for LLMAJ learning curation handler (learning-lineage .3)."""
from __future__ import annotations

from unittest.mock import patch

from factory.events.runtime.learning_handlers import curation as curation_mod
from factory.events.runtime.learning_handlers.curation import handle_learning_curation
from factory.events.runtime.models import Event
from factory.graph.mcp.core_models import EntityData, EntityLookupData, NeighborsData
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.deterministic import MemoryGetOutput
from factory.mcp_utils.runtime.tool_result import ToolResult


def _event(**overrides) -> Event:
    payload = {"memory_id": "mem-1", "run_id": "run-1", "domain_class": "code-review"}
    payload.update(overrides)
    return Event(id="evt-1", source="events.learning", type="memory.learning_stored", payload=payload)


def _entity_lookup_result(*, entity: EntityData | None) -> ToolResult[EntityLookupData]:
    return ToolResult(data=EntityLookupData(
        found=entity is not None,
        entity_id="learning-mem-1",
        entity=entity,
    ))


def _neighbors_result(neighbors: list[EntityData]) -> ToolResult[NeighborsData]:
    return ToolResult(data=NeighborsData(
        entity_id="learning-mem-1", neighbors=neighbors, count=len(neighbors),
    ))


class _Invoker:
    def __init__(self, score: float = 0.8) -> None:
        self.score = score
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, tool_name: str, **kwargs):
        self.calls.append((tool_name, kwargs))
        if tool_name == "graph_get_entity":
            return _entity_lookup_result(entity=EntityData(
                id=kwargs["entity_id"],
                type="Learning",
                properties={"memory_id": "mem-1", "run_id": "run-1", "domain_class": "code-review"},
            ))
        if tool_name == "memory_get":
            return ToolResult(data=MemoryGetOutput(
                memory_id="mem-1", found=True, memory=MemoryData(
                    id="mem-1", user_id="kiro-agent",
                    content="Prefer precise failing-case evidence before changing prompts.",
                    memory_type="long_term", category="fact", metadata={},
                    relevance_score=1.0, created_at="2026-01-01T00:00:00Z",
                ),
            ))
        if tool_name == "graph_get_neighbors":
            return _neighbors_result([EntityData(
                id="eval-auto-run-1", type="Eval", properties={"score": 0.4},
            )])
        if tool_name == "learning_compute_reward":
            return ToolResult(ok=True, data={
                "signals": [], "source_id": "llm-judge", "scalar": self.score,
                "verdict": "rewarded", "reward_value": self.score * 100,
                "wallet_id": "wallet-kiro-agent", "provenance": {},
                "scoring": {"f1": self.score},
                "raw": {"scoring": {"f1": self.score}},
            }).model_dump(mode="json")
        return {"ok": True}


def _updated_props(invoker: _Invoker) -> dict:
    updates = [kw for tool, kw in invoker.calls if tool == "graph_update_entity"]
    assert updates
    return updates[-1]["properties"]


def test_useful_learning_is_curated_but_not_suppressed() -> None:
    invoker = _Invoker(score=0.82)
    result = handle_learning_curation(_event(), invoker)

    assert result["status"] == "learning_curated"
    assert result["verdict"] == "useful"
    assert result["suppressed"] is False
    props = _updated_props(invoker)
    assert props["curated_verdict"] == "useful"
    assert props["suppressed"] is False
    assert any(tool == "graph_add_relationship" and kw["relationship_type"] == "curated_by" for tool, kw in invoker.calls)


def test_harmful_learning_is_marked_suppressed_on_graph() -> None:
    invoker = _Invoker(score=0.1)
    result = handle_learning_curation(_event(), invoker)

    assert result["verdict"] == "harmful"
    assert result["suppressed"] is True
    props = _updated_props(invoker)
    assert props["curated_verdict"] == "harmful"
    assert props["suppressed"] is True


def test_redundant_learning_is_marked_suppressed_on_graph() -> None:
    invoker = _Invoker(score=0.45)
    result = handle_learning_curation(_event(), invoker)

    assert result["verdict"] == "redundant"
    assert result["suppressed"] is True


def test_skips_without_memory_id() -> None:
    result = handle_learning_curation(_event(memory_id=""), _Invoker())
    assert result == {"skipped": True, "reason": "no_memory_id"}


def test_missing_learning_node_skips_without_writing() -> None:
    def invoker(tool_name: str, **kwargs):
        if tool_name == "graph_get_entity":
            return _entity_lookup_result(entity=None)
        raise AssertionError(f"unexpected write after missing node: {tool_name}")

    with patch.object(curation_mod.time, "sleep", return_value=None):
        result = handle_learning_curation(_event(), invoker)
    assert result["skipped"] is True
    assert result["reason"] == "learning_node_missing"


def test_curation_retries_when_lineage_node_not_yet_created() -> None:
    """Regression: .2 lineage and .3 curation race on memory.learning_stored
    (both subscribe, dispatch.py runs each in its own daemon thread with no
    ordering guarantee). If .3 checks before .2 has written the node, it must
    retry rather than permanently skip with learning_node_missing."""
    invoker = _Invoker(score=0.9)
    lookups: list[str] = []
    real_call = invoker.__call__

    def flaky_call(tool_name: str, **kwargs):
        if tool_name == "graph_get_entity":
            lookups.append(kwargs["entity_id"])
            if len(lookups) < 3:
                invoker.calls.append((tool_name, kwargs))
                return _entity_lookup_result(entity=None)
        return real_call(tool_name, **kwargs)

    with patch.object(curation_mod.time, "sleep", return_value=None):
        result = handle_learning_curation(_event(), flaky_call)

    assert len(lookups) == 3
    assert result["status"] == "learning_curated"
    assert result["verdict"] == "useful"


def test_curation_failure_is_isolated() -> None:
    def invoker(*_args, **_kwargs):
        raise RuntimeError("graph down")

    with patch.object(curation_mod.time, "sleep", return_value=None):
        result = handle_learning_curation(_event(), invoker)
    assert result["status"] == "curation_error"
    assert result["error"] == "curation_failed"


def test_failed_graph_lookup_keeps_missing_node_fallback() -> None:
    def invoker(tool_name: str, **_kwargs):
        if tool_name == "graph_get_entity":
            return ToolResult(ok=False, data=None, error="graph unavailable")
        raise AssertionError(f"unexpected tool: {tool_name}")

    with patch.object(curation_mod.time, "sleep", return_value=None):
        result = handle_learning_curation(_event(), invoker)

    assert result["skipped"] is True
    assert result["reason"] == "learning_node_missing"
