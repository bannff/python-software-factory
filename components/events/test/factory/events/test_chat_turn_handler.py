"""Chat-turn reward handler tests (bd:python-factory-pfvo9 slice 2)."""

from __future__ import annotations

from factory.events.runtime.chat_turn_handler import handle_chat_turn_reward
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult, set_service


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1]


def _event(output="A detailed, helpful answer that is well above the gate.",
           agent_id="companion-x-default"):
    return Event(
        source="agent.chat",
        type="chat.turn.completed",
        payload={
            "run_id": "chat-abc123",
            "agent_id": agent_id,
            "workflow_type": "chat",
            "input_summary": "how do I reverse a list?",
            "output_summary": output,
        },
        principal_id="kiro-agent",
    )


def test_chat_turn_emits_reward_when_source_signals() -> None:
    published: list[tuple[str, dict]] = []
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))

    def invoker(tool: str, **kwargs):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            # llm-judge produced a signal
            return ToolResult(ok=True, data={
                "signals": [],
                "source_id": "llm-judge",
                "scalar": 0.8,
                "verdict": "rewarded",
                "reward_value": 80.0,
                "wallet_id": "wallet-kiro-agent",
                "provenance": {"evaluators": ["helpfulness", "coherence"]},
                "raw": {"scoring": {"f1": 0.8}},
                "scoring": {"f1": 0.8},
            }).model_dump(mode="json")
        if tool == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-1", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")

    result = handle_chat_turn_reward(_event(), invoker)

    assert result["reward"]["reward_value"] == 80.0
    assert [t for t, _ in published] == ["reward.computed"]
    payload = published[0][1]
    assert payload["score"] == 0.8
    assert payload["source_id"] == "llm-judge"
    # persona id → domain_class so memory tags {agent_id}-learnings (recall loop)
    assert payload["domain_class"] == "companion-x-default"


def test_chat_turn_skips_when_all_sources_abstain() -> None:
    published: list[tuple[str, dict]] = []
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))

    def invoker(tool: str, **kwargs):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            return ToolResult(ok=True, data={
                "signals": [], "source_id": "", "scalar": 0.0,
                "verdict": "no_reward", "reward_value": 0.0,
                "wallet_id": "wallet-kiro-agent", "provenance": {},
                "raw": {}, "scoring": {},
            }).model_dump(mode="json")
        if tool == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")

    result = handle_chat_turn_reward(_event(output="ok"), invoker)
    assert result["skipped"] is True
    assert published == []  # no reward spam on abstained turns


def test_chat_turn_skips_without_output() -> None:
    result = handle_chat_turn_reward(_event(output=""), lambda *a, **k: {})
    assert result["skipped"] is True
