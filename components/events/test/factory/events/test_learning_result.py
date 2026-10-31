"""Learning envelope normalization and handler failure regressions."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from hypothesis import given, settings, strategies as st

from factory.events.runtime.chat_turn_handler import (
    handle_chat_feedback,
    handle_chat_turn_reward,
)
from factory.events.runtime.generic_score_dispatch import (
    ScoringPolicyEntry,
    handle_generic_score_dispatch,
)
from factory.events.runtime.learning_result import normalize_learning_result
from factory.events.runtime.models import Event
from factory.events.runtime.rewards_handler import handle_rewards_process
from factory.events.runtime.telemetry_handler import handle_telemetry_reward
from factory.mcp_utils.interface import ToolResult, set_service


def _capture_learning_signal(published):
    """Caller-bound service fake so protected signals reach ``published``."""
    return lambda caller: lambda target, **call: (
        published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
        {"ok": True},
    )[1]


def _success_data() -> dict[str, object]:
    return {
        "signals": [],
        "source_id": "llm-judge",
        "scalar": 0.8,
        "verdict": "rewarded",
        "reward_value": 80.0,
        "wallet_id": "wallet-kiro-agent",
        "provenance": {"fixture": True},
        "raw": {"scoring": {"f1": 0.8}},
        "scoring": {"f1": 0.8},
    }


def test_normalizer_rejects_bare_and_unknown_success_mappings() -> None:
    assert normalize_learning_result(_success_data()) is None
    assert normalize_learning_result({**_success_data(), "unexpected": True}) is None


def test_normalizer_accepts_only_typed_or_serialized_v1_success() -> None:
    typed = ToolResult(ok=True, data=_success_data())
    assert normalize_learning_result(typed) is not None
    assert normalize_learning_result(typed.model_dump(mode="json")) is not None


def test_normalizer_rejects_typed_and_serialized_failures() -> None:
    failed = ToolResult(ok=False, error="learning backend unavailable")
    assert normalize_learning_result(failed) is None
    assert normalize_learning_result(failed.model_dump(mode="json")) is None
    assert normalize_learning_result(None) is None


@settings(max_examples=40, deadline=None)
@given(scalar=st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False))
def test_normalizer_preserves_valid_canonical_scalars(scalar: float) -> None:
    payload = {**_success_data(), "scalar": scalar}
    normalized = normalize_learning_result(ToolResult(ok=True, data=payload))
    assert normalized is not None
    assert normalized["scalar"] == scalar


def test_normalizer_rejects_out_of_bounds_authoritative_values() -> None:
    payload = _success_data()
    assert normalize_learning_result(
        ToolResult(ok=True, data={**payload, "reward_value": 1_000_001.0})
    ) is None
    assert normalize_learning_result(
        ToolResult(ok=True, data={**payload, "wallet_id": "bad wallet"})
    ) is None

def _failed_invoker(tool: str, **_kwargs):
    assert tool == "learning_compute_reward"
    return ToolResult(ok=False, error="learning unavailable")


def test_rewards_handler_skips_failed_learning_envelope() -> None:
    event = Event(
        source="agent.graph", type="graph.completed",
        payload={"run_id": "run-1", "graph_id": "graph-1"},
    )
    result = handle_rewards_process(event, _failed_invoker)
    assert result == {"skipped": True, "reason": "reward computation failed"}


def test_chat_turn_handler_skips_failed_learning_envelope() -> None:
    event = Event(
        source="agent.chat", type="chat.turn.completed",
        payload={"run_id": "chat-1", "agent_id": "agent-1", "output_summary": "A" * 50},
    )
    result = handle_chat_turn_reward(event, _failed_invoker)
    assert result == {"skipped": True, "error": "reward_computation_failed"}


def test_chat_feedback_handler_skips_failed_learning_envelope() -> None:
    event = Event(
        source="next-dashboard-chat", type="chat.feedback",
        payload={"verdict": "up", "agent_id": "agent-1", "message_id": "m-1"},
    )
    result = handle_chat_feedback(event, _failed_invoker)
    assert result == {"skipped": True, "error": "reward_computation_failed"}


def test_telemetry_handler_skips_failed_learning_envelope() -> None:
    event = Event(
        source="events.auto-metrics", type="metrics.record",
        payload={"run_id": "run-1", "tool_error_rate": 0.4},
    )
    result = handle_telemetry_reward(event, _failed_invoker)
    assert result == {"skipped": True, "error": "reward_computation_failed"}


def test_generic_handler_skips_failed_learning_envelope() -> None:
    event = Event(
        source="workflow", type="code_review.completed",
        payload={"run_id": "run-1", "workflow_id": "wf-1"},
    )
    with patch(
        "factory.events.runtime.generic_score_dispatch.load_scoring_policy",
        return_value=[ScoringPolicyEntry(pattern="code_review.completed", source_tag="review")],
    ):
        result = handle_generic_score_dispatch(event, _failed_invoker)
    assert result == {"skipped": True, "error": "reward_computation_failed"}


def test_chat_turn_handler_accepts_typed_success_envelope() -> None:
    published: list[tuple[str, dict]] = []
    set_service("tool_invoker_for_caller", _capture_learning_signal(published))

    def invoker(tool: str, **kwargs):
        if tool == "learning_compute_reward":
            return ToolResult(ok=True, data=_success_data())
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-1"}
        raise AssertionError(f"unexpected tool: {tool}")

    event = Event(
        source="agent.chat", type="chat.turn.completed",
        payload={"run_id": "chat-1", "agent_id": "agent-1", "output_summary": "A" * 50},
    )
    result = handle_chat_turn_reward(event, invoker)
    assert result["reward"]["source_id"] == "llm-judge"
    assert result["reward"]["reward_value"] == 80.0
    assert [event_type for event_type, _ in published] == ["reward.computed"]


@pytest.mark.parametrize(
    "data",
    [
        {"text": "x" * 65_537},
        {"items": ["x" * 60_000] * 20},
        {"items": [10**9 + 1]},
        {"items": [[[[[[[[[[[[["too-deep"]]]]]]]]]]]]]},
    ],
)
def test_typed_learning_envelope_rejects_bounded_json_violations(data) -> None:
    payload = {**_success_data(), "raw": data}
    assert normalize_learning_result(ToolResult(ok=True, data=payload)) is None


@pytest.mark.parametrize(
    ("items", "valid"),
    [(256, True), (257, False)],
)
def test_typed_learning_envelope_enforces_exact_evidence_item_boundaries(
    items: int, valid: bool,
) -> None:
    for raw in (
        {"object": {str(index): index for index in range(items)}},
        {"list": list(range(items))},
    ):
        payload = {**_success_data(), "raw": raw}
        normalized = normalize_learning_result(
            ToolResult(ok=True, data=payload),
        )
        assert (normalized is not None) is valid
