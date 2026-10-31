"""Learning fan-out compatibility with typed and serialized MCP envelopes."""
from __future__ import annotations

import pytest

from factory.events.runtime.learning_handlers._common import _already_published
from factory.events.runtime.learning_handlers.convergence import handle_convergence_check
from factory.events.runtime.learning_handlers.curation import handle_learning_curation
from factory.events.runtime.learning_handlers.memory import handle_memory_learning
from factory.events.runtime.models import Event
from factory.events.runtime.rewards_handler import _emit_reward_event
from factory.events.mcp.contracts.base import EventData
from factory.events.mcp.contracts.deterministic import QueryEventsOutput
from factory.graph.mcp.core_models import EntityData, EntityLookupData, NeighborsData
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.deterministic import MemoryGetOutput
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.metrics.mcp.contracts.operational import DriftOutput, RecordOutput
from factory.mcp_utils.interface import ToolResult, set_service


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append(call["arguments"]["payload"]),
        {"ok": True},
    )[1]


def _wire(result: ToolResult) -> dict:
    return result.model_dump(mode="json")


def _learning_result(score: float = 0.8) -> dict:
    return _wire(ToolResult(ok=True, data={
        "signals": [], "source_id": "llm-judge", "scalar": score,
        "verdict": "rewarded", "reward_value": score * 100,
        "wallet_id": "wallet-kiro-agent", "provenance": {},
        "raw": {"scoring": {"f1": score}}, "scoring": {"f1": score},
    }))


def test_event_dedup_reads_typed_and_serialized_query_results() -> None:
    event_data = EventData(
        id="evt-1", type="reward.computed", source="events.rewards",
        timestamp="2026-01-01T00:00:00Z", payload={"idempotency_key": "k"},
    )
    output = QueryEventsOutput(events=[event_data], total=1)
    for result in (ToolResult(data=output), _wire(ToolResult(data=output))):
        assert _already_published(
            lambda _tool, **_kwargs: result, "reward.computed", "k",
        ) is True


def test_memory_learning_reads_serialized_store_success() -> None:
    memory = MemoryData(
        id="mem-1", user_id="kiro-agent", content="fact",
        memory_type="long_term", category="fact", metadata={},
        relevance_score=1.0, created_at="2026-01-01T00:00:00Z",
    )
    published: list[dict] = []
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))

    def invoke(name: str, **kwargs):
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "memory_memory_store":
            return _wire(ToolResult(data=MemoryStoreOutput(stored=True, memory=memory)))
        if name == "events_publish":
            published.append(kwargs["payload"])
            return {"event_id": "evt-1"}
        raise AssertionError(name)

    result = handle_memory_learning(
        Event(source="events.rewards", type="reward.computed",
              payload={"run_id": "run-1", "workflow_run_id": "wf-1"}),
        invoke,
    )
    assert result["memory_id"] == "mem-1"
    assert published[0]["memory_id"] == "mem-1"


def test_curation_reads_serialized_graph_and_memory_results() -> None:
    entity = EntityData(
        id="learning-mem-1", type="Learning",
        properties={"run_id": "run-1", "domain_class": "code-review"},
    )
    memory = MemoryData(
        id="mem-1", user_id="kiro-agent", content="Prefer precise evidence.",
        memory_type="long_term", category="fact", metadata={},
        relevance_score=1.0, created_at="2026-01-01T00:00:00Z",
    )
    neighbors = NeighborsData(
        entity_id=entity.id,
        neighbors=[EntityData(id="eval-1", type="Eval", properties={})], count=1,
    )
    calls: list[str] = []

    def invoke(name: str, **kwargs):
        calls.append(name)
        if name == "graph_get_entity":
            return _wire(ToolResult(data=EntityLookupData(
                found=True, entity_id=entity.id, entity=entity,
            )))
        if name == "memory_get":
            return _wire(ToolResult(data=MemoryGetOutput(
                memory_id="mem-1", found=True, memory=memory,
            )))
        if name == "graph_get_neighbors":
            return _wire(ToolResult(data=neighbors))
        if name == "learning_compute_reward":
            return _learning_result()
        return {"ok": True}

    result = handle_learning_curation(
        Event(id="evt-1", source="events.learning", type="memory.learning_stored",
              payload={"memory_id": "mem-1", "run_id": "run-1",
                       "domain_class": "code-review"}),
        invoke,
    )
    assert result["status"] == "learning_curated"
    assert result["verdict"] == "useful"
    assert "graph_update_entity" in calls


def test_convergence_reads_serialized_metrics_results() -> None:
    published: list[dict] = []

    def invoke(name: str, **kwargs):
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "metrics_record":
            return _wire(ToolResult(data=RecordOutput(
                ok=True, metric_id=kwargs["metric_id"], value=0.0, timestamp=1.0,
            )))
        if name == "metrics_detect_drift":
            return _wire(ToolResult(data=DriftOutput(
                metric_id="pipeline-f1", drifted=False,
                baseline_mean=0.7, current_mean=0.71,
            )))
        if name == "events_publish":
            published.append(kwargs["payload"])
            return {"event_id": "evt-1"}
        raise AssertionError(name)

    result = handle_convergence_check(
        Event(source="events.rewards", type="reward.computed", payload={
            "run_id": "run-1", "workflow_run_id": "wf-1", "graph_id": "g",
            "source_id": "gt-findings", "score": 0.8,
        }),
        invoke,
    )
    assert result["metrics_recorded"] == 7
    assert result["converged"] is True
    assert published


def test_reward_event_publication_failure_is_isolated() -> None:
    def invoke(name: str, **kwargs):
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "events_publish":
            raise RuntimeError("event bus unavailable")
        raise AssertionError(name)

    result = _emit_reward_event(
        invoke,
        Event(source="events.rewards", type="reward.computed",
              payload={"run_id": "run-1", "workflow_run_id": "wf-1"}),
        {**{
            "source_id": "gt-findings", "scalar": 0.8, "verdict": "rewarded",
            "reward_value": 80.0, "wallet_id": "wallet-kiro-agent",
            "provenance": {},
        }, "scoring": {"f1": 0.8}},
    )
    assert result["reward_value"] == 80.0
    assert result["idempotency_key"] == "reward:wf-1:v1"
