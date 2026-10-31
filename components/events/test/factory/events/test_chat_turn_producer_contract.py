"""Producer contract: WorkCompletedEmitterPlugin payload ↔ chat-turn
reward handler ingestion (epic #124 S4a; agent://SymbolicFly risk R7).

Pins the four handler-consumed keys and the 65_536-char truncation
against the handler's real ingestion path (``chat_turn_handler``), and
proves the plugin payload round-trips through
``handle_chat_turn_reward`` — zero shape repair on either side.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from factory.agent.interface import WorkCompletedEmitterPlugin, chat_turn_completed_payload
from factory.events.runtime.chat_turn_handler import (
    _MAX_FEEDBACK_TEXT, handle_chat_turn_reward,
)
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult, set_service


class _Request:
    """Minimal RuntimeInvocation stand-in (only fields the emitter reads)."""

    def __init__(self) -> None:
        self.invocation_id = "chat-abc123"
        self.agent_id = "companion-x-default"
        self.prompt = "hello"
        self.tenant_id = "tenant-1"
        self.owner_id = "owner-1"
        self.thread_id = "thread-1"


class _Agent:
    messages: list[dict[str, Any]] = [
        {"role": "assistant", "content": [{"text": "humans reply"}]},
    ]


class _Event:
    agent = _Agent()
    cancel = False
    result = None


_HANDLER_KEYS = {"run_id", "agent_id", "input_summary", "output_summary"}

_LEARN_DATA = {
    "signals": [], "source_id": "llm-judge", "verdict": "rewarded",
    "scalar": 0.8, "reward_value": 80.0, "wallet_id": "wallet-kiro-agent",
    "provenance": {"evaluators": ["helpfulness"]}, "raw": {},
    "scoring": {"f1": 0.8},
}


def _payload(request: Any = None, event: Any = None) -> dict[str, Any]:
    return chat_turn_completed_payload(request or _Request(), event or _Event())


def _reward_invoker(seen: list[dict[str, Any]]) -> Callable[..., Any]:
    def invoker(tool: str, **kwargs: Any) -> Any:
        seen.append({"tool": tool, **kwargs})
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "learning_compute_reward":
            return ToolResult(ok=True, data=_LEARN_DATA).model_dump(mode="json")
        if tool == "events_publish":
            return {"event_id": "evt-1", "status": "published"}
        raise AssertionError(f"unexpected tool: {tool}")
    return invoker


def test_plugin_payload_keys_are_exactly_handler_ingested() -> None:
    payload = _payload()
    assert set(payload) - {"idempotency_key"} == _HANDLER_KEYS
    assert payload["run_id"] == "chat-abc123"
    assert payload["agent_id"] == "companion-x-default"
    assert payload["input_summary"] == "hello"
    assert payload["output_summary"] == "humans reply"
    # Identity never appears in the payload (S5 landing-zone discipline):
    # it rides the MCP call envelope instead.
    assert not {"tenant_id", "principal_id", "owner_id", "user_id"} & set(payload)


def test_plugin_truncates_summaries_at_65536_chars() -> None:
    assert _MAX_FEEDBACK_TEXT == 65_536  # handler ingest limit, unchanged
    request = _Request()
    event = _Event()
    event.agent = _Agent()
    request.prompt = "x" * (_MAX_FEEDBACK_TEXT + 100)
    event.agent.messages = [
        {"role": "assistant",
         "content": [{"text": "y" * (_MAX_FEEDBACK_TEXT + 100)}]},
    ]
    payload = _payload(request, event)
    assert len(payload["input_summary"]) == 65_536
    assert len(payload["output_summary"]) == 65_536
    # Handler-side slicing of the same payload is a no-op → no drift:
    for key in ("input_summary", "output_summary"):
        assert str(payload[key])[:_MAX_FEEDBACK_TEXT] == payload[key]


def test_plugin_payload_scores_through_real_handler() -> None:
    """Round-trip: handler ingests the plugin payload via the real seam
    (learning_compute_reward), rewards, and emits reward.computed whose
    domain_class maps agent_id → {agent_id}-learnings (recall loop)."""
    published: list[tuple[str, dict[str, Any]]] = []
    from factory.mcp_utils.interface import get_service
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", lambda _caller: (
        lambda target, **call: (
            published.append(
                (call["arguments"]["event_type"], call["arguments"]["payload"]),
            ), {"ok": True})[1]
    ))
    try:
        seen: list[dict[str, Any]] = []
        event = Event(source="agent", type="chat.turn.completed", payload=_payload())
        result = handle_chat_turn_reward(event, _reward_invoker(seen))
    finally:
        set_service("tool_invoker_for_caller", previous)

    compute = [call for call in seen if call["tool"] == "learning_compute_reward"]
    assert len(compute) == 1
    ingested = compute[0]
    assert ingested["run_id"] == "chat-abc123"
    assert ingested["domain_class"] == "companion-x-default"
    assert ingested["workflow_type"] == "chat"
    assert ingested["input_summary"] == "hello"
    assert ingested["output_summary"] == "humans reply"

    assert result["run_id"] == "chat-abc123"
    assert result["agent_id"] == "companion-x-default"
    assert result["reward"]["reward_value"] == 80.0
    assert [event_type for event_type, _ in published] == ["reward.computed"]
    assert published[0][1]["domain_class"] == "companion-x-default"


def test_plugin_registers_after_invocation_callback() -> None:
    """Wire-up proof: the plugin registers a runnable AfterInvocationEvent
    callback on a real strands HookRegistry (no unbound-request crash)."""
    from strands.hooks import AfterInvocationEvent, HookRegistry

    registry = HookRegistry()
    WorkCompletedEmitterPlugin(invoker=None).register_hooks(registry)
    event = AfterInvocationEvent(agent=None, invocation_state={}, result=None)
    registry.invoke_callbacks(event)  # request unbound → plugin exits quietly
