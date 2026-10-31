"""bd python-factory-7ut47 — rewards_handler + memory handler key off domain_class.

Phase E behavior tests for the two reward-side handlers. Improvement
handler + dispatch_args coverage live in
``test_handlers_domain_class_improvement.py`` to keep both files under
the 200 LOC ceiling.
"""

from __future__ import annotations

from typing import Any

from factory.events.runtime.learning_handlers import handle_memory_learning
from factory.events.runtime.models import Event
from factory.events.runtime.rewards_handler import handle_rewards_process
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.mcp_utils.interface import ToolResult


def _stored_memory() -> ToolResult[MemoryStoreOutput]:
    return ToolResult(data=MemoryStoreOutput(stored=True, memory=MemoryData(
        id="mem-1", user_id="kiro-agent", content="fact", memory_type="long_term",
        category="fact", metadata={}, relevance_score=1.0, created_at="2026-01-01T00:00:00Z")))


class _Recorder:
    def __init__(self, returns: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._returns = returns or {}

    def __call__(self, tool: str, **kwargs: Any) -> Any:
        self.calls.append((tool, kwargs))
        if tool in self._returns:
            v = self._returns[tool]
            value = v(**kwargs) if callable(v) else v
            if tool == "learning_compute_reward" and isinstance(value, dict):
                return ToolResult(ok=True, data=value).model_dump(mode="json")
            return value
        return {}


def test_rewards_handler_forwards_domain_class_to_games() -> None:
    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "learning_compute_reward": {
            "signals": [], "source_id": "gt-findings", "scalar": 0.5,
            "verdict": "rewarded", "reward_value": 50.0,
            "wallet_id": "wallet-kiro-agent",
            "provenance": {"precision": 0.5, "recall": 0.5},
            "scoring": {"f1": 0.5, "precision": 0.5, "recall": 0.5},
            "raw": {
                "scoring": {"f1": 0.5, "precision": 0.5, "recall": 0.5,
                            "true_positives": 0, "false_positives": 0,
                            "false_negatives": 0},
                "blockchain": {"amount": 50.0, "wallet_id": "wallet-kiro-agent"},
                "memory": {"stored": False},
            },
        },
        "events_publish": {"event_id": "evt-1"},
    })

    event = Event(
        source="events.dispatch",
        type="graph.completed",
        payload={
            "run_id": "run-WineApp-1",
            "workflow_run_id": "wf-1",
            "workflow_id": "wine-tasting",
            "domain_class": "wine",
            "vuln_class": "TASTING",
            "workflow_type": "dast",
            "target_app": "WineApp",
        },
    )

    result = handle_rewards_process(event, invoker)

    rl_calls = [c for c in invoker.calls if c[0] == "learning_compute_reward"]
    assert rl_calls
    _, kwargs = rl_calls[0]
    assert kwargs["domain_class"] == "wine"
    assert kwargs["vuln_class"] == "TASTING"
    assert result["rl"]["scoring"]["f1"] == 0.5
    assert result["rl"]["source_id"] == "gt-findings"


def test_rewards_handler_falls_back_to_vuln_class_when_domain_missing() -> None:
    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "learning_compute_reward": {
            "signals": [], "source_id": "gt-findings", "scalar": 0.0,
            "verdict": "no_reward", "reward_value": 0.0,
            "wallet_id": "wallet-kiro-agent", "provenance": {},
            "scoring": {"f1": 0.0}, "raw": {"scoring": {"f1": 0.0}},
        },
        "events_publish": {"event_id": "evt-1"},
    })
    event = Event(
        source="events.dispatch",
        type="graph.completed",
        payload={
            "run_id": "run-1", "workflow_run_id": "wf-1",
            "vuln_class": "IDOR",
        },
    )
    handle_rewards_process(event, invoker)
    rl_calls = [c for c in invoker.calls if c[0] == "learning_compute_reward"]
    _, kwargs = rl_calls[0]
    assert kwargs["domain_class"] == "IDOR"
    assert kwargs["vuln_class"] == "IDOR"


def test_memory_handler_builds_tags_off_domain_class() -> None:
    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "memory_memory_store": _stored_memory(),
        "events_publish": {"event_id": "evt-mem"},
    })
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "run-1", "workflow_run_id": "wf-1",
            "domain_class": "wine", "vuln_class": "TASTING",
            "workflow_type": "dast", "target_app": "WineApp",
            "score": 0.5, "precision": 0.5, "recall": 0.5,
            "true_positives": 1, "false_positives": 0, "false_negatives": 0,
        },
    )
    handle_memory_learning(event, invoker)

    mem_calls = [c for c in invoker.calls if c[0] == "memory_memory_store"]
    _, kwargs = mem_calls[0]
    tags = kwargs["metadata"]["tags"]
    assert "wine" in tags
    assert "wine-learnings" in tags
    assert kwargs["metadata"]["domain_class"] == "wine"
    assert kwargs["metadata"]["vuln_class"] == "TASTING"
    assert "wine" in kwargs["content"]


def test_memory_handler_falls_back_to_vuln_class_for_tag() -> None:
    invoker = _Recorder({
        "events_query_events": {"events": [], "total": 0},
        "memory_memory_store": _stored_memory(),
        "events_publish": {"event_id": "evt-mem"},
    })
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "run-1", "workflow_run_id": "wf-1",
            "vuln_class": "IDOR",
            "workflow_type": "dast", "target_app": "WebGoat",
            "score": 0.5, "precision": 0.5, "recall": 0.5,
            "true_positives": 1, "false_positives": 0, "false_negatives": 0,
        },
    )
    handle_memory_learning(event, invoker)
    mem_calls = [c for c in invoker.calls if c[0] == "memory_memory_store"]
    _, kwargs = mem_calls[0]
    tags = kwargs["metadata"]["tags"]
    assert "IDOR" in tags
    assert "IDOR-learnings" in tags
