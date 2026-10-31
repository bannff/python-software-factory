"""Outcome-driven corrective recall tests (bd:python-factory-3oxx0).

A down-voted answer must be stored as a recall-matchable AVOID learning (real
substance + framing), not a numeric scoreboard. Workflow/GT runs keep the
byte-identical scoreboard content.
"""

from __future__ import annotations

from factory.events.runtime.learning_handlers import handle_memory_learning
from factory.events.runtime.models import Event
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.mcp_utils.interface import ToolResult


def _stored_memory() -> ToolResult[MemoryStoreOutput]:
    return ToolResult(data=MemoryStoreOutput(stored=True, memory=MemoryData(
        id="mem-1", user_id="kiro-agent", content="fact", memory_type="long_term",
        category="fact", metadata={}, relevance_score=1.0, created_at="2026-01-01T00:00:00Z")))


def _store_invoker(stored: list):
    def _invoke(tool: str, **kwargs):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "memory_memory_store":
            stored.append(kwargs)
            return _stored_memory()
        if tool == "events_publish":
            return {"event_id": "e", "status": "published"}
        return {}
    return _invoke


def _reward_event(verdict: str, feedback_text: str, domain="wine-pairing"):
    return Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "feedback-1", "workflow_run_id": "feedback-1",
            "domain_class": domain, "verdict": verdict, "score": 0.0,
            "provenance": {"feedback_verdict": "down" if verdict == "penalized" else "up",
                           "feedback_text": feedback_text},
        },
        principal_id="kiro-agent",
    )


def test_down_voted_answer_stored_as_avoid_correction() -> None:
    stored: list = []
    handle_memory_learning(
        _reward_event("penalized", "Pair a dry Riesling with a ribeye steak."),
        _store_invoker(stored))
    kw = stored[0]
    assert "AVOID" in kw["content"]
    assert "Riesling with a ribeye" in kw["content"]      # real substance for recall match
    assert kw["metadata"]["verdict"] == "penalized"
    assert "wine-pairing-learnings" in kw["metadata"]["tags"]


def test_up_voted_answer_stored_as_good_correction() -> None:
    stored: list = []
    handle_memory_learning(
        _reward_event("rewarded", "Riesling pairs with spicy Thai food."),
        _store_invoker(stored))
    kw = stored[0]
    assert "GOOD" in kw["content"]
    assert "spicy Thai food" in kw["content"]


def test_workflow_run_keeps_scoreboard_byte_identical() -> None:
    stored: list = []
    event = Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": "r1", "workflow_run_id": "r1", "domain_class": "idor",
            "verdict": "rewarded", "score": 0.82, "precision": 0.8, "recall": 0.84,
            "target_app": "WebGoat", "workflow_type": "dast",
            # No provenance.feedback_text → scoreboard branch.
        },
        principal_id="kiro-agent",
    )
    handle_memory_learning(event, _store_invoker(stored))
    content = stored[0]["content"]
    assert content.startswith("RL [dast]")  # unchanged metrics scoreboard
    assert "F1=0.82" in content
