"""Integration: chat turn → REAL learning seam → reward.computed.

Exercises the actual ``LearningRuntime`` + ``LlmJudgeRewardSource`` behind
``handle_chat_turn_reward`` (only the leaf evals/memory tools are stubbed),
proving the slice-2 chain composes without external services
(bd:python-factory-pfvo9).
"""

from __future__ import annotations

from factory.events.runtime.chat_turn_handler import handle_chat_turn_reward
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult, set_service
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.learning.runtime.adapters.gt_findings import GtFindingsRewardSource
from factory.learning.runtime.adapters.llm_judge import LlmJudgeRewardSource


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1]


def _real_learning_invoker(published: list, judge_score: float):
    """An invoker that routes learning_compute_reward to the REAL runtime."""
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    reg.register_builtin(LlmJudgeRewardSource())
    runtime = LearningRuntime(reg)

    def _inner(tool: str, **kwargs):
        # Leaf tool the llm-judge source calls — stub the LLM eval only.
        if tool == "evals_evaluate_multi":
            return {"aggregate": {"avg_score": judge_score}}
        raise AssertionError(f"unexpected inner tool: {tool}")

    def _invoker(tool: str, **kwargs):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            run_ctx = {
                "graph_id": kwargs.get("graph_id", ""),
                "run_id": kwargs.get("run_id", ""),
                "domain_class": kwargs.get("domain_class", ""),
                "workflow_type": kwargs.get("workflow_type", "auto"),
                "input_summary": kwargs.get("input_summary", ""),
                "output_summary": kwargs.get("output_summary", ""),
            }
            return ToolResult(
                ok=True, data=runtime.compute(run_ctx, _inner),
            ).model_dump(mode="json")
        if tool == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")

    return _invoker


def test_chat_turn_closes_loop_through_real_learning_seam() -> None:
    published: list = []
    event = Event(
        source="agent.chat",
        type="chat.turn.completed",
        payload={
            "run_id": "chat-int-1",
            "agent_id": "wine-pairing",
            "workflow_type": "chat",
            "input_summary": "What pairs with a dry Riesling?",
            "output_summary": (
                "A dry Riesling pairs beautifully with spicy Thai food, "
                "pork, and soft cheeses — its acidity cuts richness."
            ),
        },
        principal_id="kiro-agent",
    )

    invoker = _real_learning_invoker(published, judge_score=0.75)
    result = handle_chat_turn_reward(event, invoker)

    # Real llm-judge source produced the winning signal (gt-findings abstained).
    assert result["reward"]["source_id"] == "llm-judge"
    assert result["reward"]["reward_value"] == 75.0
    assert [t for t, _ in published] == ["reward.computed"]
    payload = published[0][1]
    assert payload["verdict"] == "rewarded"
    # Persona id rode through to domain_class → memory will tag
    # "wine-pairing-learnings", which LearningRecallPlugin queries next turn.
    assert payload["domain_class"] == "wine-pairing"


def test_chat_turn_trivial_output_abstains_through_real_seam() -> None:
    published: list = []
    event = Event(
        source="agent.chat", type="chat.turn.completed",
        payload={"run_id": "chat-int-2", "agent_id": "wine-pairing",
                 "output_summary": "ok"},  # below llm-judge min-output gate
        principal_id="kiro-agent",
    )
    result = handle_chat_turn_reward(event, _real_learning_invoker(published, 0.9))
    assert result["skipped"] is True
    assert published == []
