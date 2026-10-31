"""Chat-feedback → reward tests (bd:python-factory-pfvo9 S2).

Runs the REAL learning runtime (user-feedback source) behind the handler;
only events_query/publish are stubbed.
"""

from __future__ import annotations

from factory.events.runtime.chat_turn_handler import handle_chat_feedback
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult, set_service
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.learning.runtime.adapters.gt_findings import GtFindingsRewardSource
from factory.learning.runtime.adapters.llm_judge import LlmJudgeRewardSource
from factory.learning.runtime.adapters.user_feedback import UserFeedbackRewardSource


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1]


def _invoker(published: list):
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    reg.register_builtin(LlmJudgeRewardSource())
    reg.register_builtin(UserFeedbackRewardSource())
    runtime = LearningRuntime(reg)

    def _invoke(tool: str, **kwargs):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            run_ctx = {
                "graph_id": "", "run_id": kwargs.get("run_id", ""),
                "domain_class": kwargs.get("domain_class", ""),
                "workflow_type": kwargs.get("workflow_type", "auto"),
                "output_summary": kwargs.get("output_summary", ""),
                "feedback_verdict": kwargs.get("feedback_verdict", ""),
            }
            return ToolResult(
                ok=True, data=runtime.compute(run_ctx, None),
            ).model_dump(mode="json")
        if tool == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")

    return _invoke


def _feedback_event(verdict="up", agent_id="wine-pairing"):
    return Event(
        source="next-dashboard-chat", type="chat.feedback",
        payload={"verdict": verdict, "agent_id": agent_id,
                 "thread_id": "t1", "message_id": "m1"},
        principal_id="kiro-agent",
    )


def test_thumbs_up_rewards_via_user_feedback_source() -> None:
    published: list = []
    result = handle_chat_feedback(_feedback_event("up"), _invoker(published))
    assert result["reward"]["source_id"] == "user-feedback"
    assert result["reward"]["reward_value"] == 100.0
    assert result["reward"]["verdict"] == "rewarded"
    et, payload = published[0]
    assert et == "reward.computed"
    # Persona id → domain_class so memory tags {agent_id}-learnings (recall).
    assert payload["domain_class"] == "wine-pairing"


def test_thumbs_down_is_penalized_and_mints_nothing() -> None:
    published: list = []
    result = handle_chat_feedback(_feedback_event("down"), _invoker(published))
    reward = result["reward"]
    assert reward["source_id"] == "user-feedback"
    assert reward["reward_value"] == 0.0       # never mints negative
    assert reward["verdict"] == "penalized"     # but is NOT "no_reward"
    # Still emits reward.computed so the down-vote is stored as a learning.
    assert [t for t, _ in published] == ["reward.computed"]


def test_non_thumbs_verdict_skips() -> None:
    result = handle_chat_feedback(_feedback_event("maybe"), lambda *a, **k: {})
    assert result["skipped"] is True
