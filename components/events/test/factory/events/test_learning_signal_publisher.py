"""Protected downstream learning-signal publisher — service-only, tenant-bound.

Covers reward.computed and memory.learning_stored: public spoof refusal,
direct-tool denial, internal Events caller success with an exact binding, and
wrong tenant/digest/type rejection.
"""
from __future__ import annotations

import asyncio
import hashlib

import pytest

from factory.events.runtime.learning_contracts import validate_learning_payload
from factory.events.runtime.runtime import EventsRuntime
from factory.events.server import create_mcp_server
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    ServiceOnlyAccessError, get_service, protected_canonical_json, set_service,
)

_TYPES = ("reward.computed", "memory.learning_stored")


def _fn(server, name: str):
    return asyncio.run(server.get_tool(name)).fn


def _reward_payload(key: str = "reward:wf-1:v1") -> dict:
    return validate_learning_payload("reward.computed", {
        "run_id": "run-1", "workflow_run_id": "wf-1",
        "idempotency_key": key,
        "tenant_id": "tenant", "principal_id": "owner", "score": 0.8,
    })


def _memory_payload(key: str = "memory:wf-1:workflow_rl") -> dict:
    return validate_learning_payload("memory.learning_stored", {
        "run_id": "run-1", "workflow_run_id": "wf-1",
        "idempotency_key": key, "summary_type": "workflow_rl",
        "tenant_id": "tenant", "principal_id": "owner",
    })


def _binding(payload: dict, *, tenant: str = "tenant", owner: str = "owner",
             event_type: str = "reward.computed", digest: str | None = None) -> dict:
    return {
        "tenant_id": tenant, "owner_id": owner, "event_type": event_type,
        "subject_id": payload["idempotency_key"], "revision": 1,
        "payload_digest": digest or hashlib.sha256(
            protected_canonical_json(payload),
        ).hexdigest(),
    }


def _sc(result: dict) -> dict:
    return result["result"]["structured_content"]


def _failed(result: dict) -> bool:
    """True when the call failed at the service body OR the transport boundary."""
    if result.get("ok") is False:
        return True
    inner = result.get("result", {})
    structured = inner.get("structured_content") if isinstance(inner, dict) else None
    return isinstance(structured, dict) and structured.get("ok") is False


def test_public_publish_refuses_both_protected_signals(tmp_path) -> None:
    server = create_mcp_server(EventsRuntime(tmp_path))
    publish = _fn(server, "events_publish")
    for event_type in _TYPES:
        result = publish(event_type=event_type, payload={}, source="attacker")
        assert result.ok is False
        assert result.error == "protected_event_requires_service"


def test_direct_service_tool_call_is_denied(tmp_path) -> None:
    server = create_mcp_server(EventsRuntime(tmp_path))
    tool = _fn(server, "events_publish_learning_signal")
    payload = _reward_payload()
    with pytest.raises(ServiceOnlyAccessError):
        tool(**_binding(payload), payload=payload)


def _composed(tmp_path):
    events = EventsRuntime(tmp_path)
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["events"])
    aggregator._lazy._cache["events"] = create_mcp_server(events)
    native = NativeEnvelopeInvoker(aggregator)
    previous_factory = get_service("tool_invoker_for_caller")
    previous_invoker = get_service("tool_invoker")
    set_service("tool_invoker_for_caller", native.for_caller)
    set_service("tool_invoker", aggregator.invoke_tool)
    return events, native, (previous_factory, previous_invoker)


def _restore(previous) -> None:
    set_service("tool_invoker_for_caller", previous[0])
    set_service("tool_invoker", previous[1])


def _invoke(native, binding: dict, payload: dict):
    return native.for_caller("events")(
        {"brick_name": "events", "tool_name": "events_publish_learning_signal"},
        arguments={**binding, "payload": payload},
        idempotency_key=f"learning-signal:{binding['event_type']}:{binding['subject_id']}",
        envelope={"tenant_id": binding["tenant_id"], "principal_id": binding["owner_id"]},
        projection=binding,
    )


@pytest.mark.parametrize("event_type", _TYPES)
def test_internal_events_caller_publishes_with_exact_binding(tmp_path, event_type) -> None:
    events, native, previous = _composed(tmp_path)
    payload = _reward_payload() if event_type == "reward.computed" else _memory_payload()
    binding = _binding(payload, event_type=event_type)
    try:
        structured = _sc(_invoke(native, binding, payload))
        assert structured["ok"] is True
        event_id = structured["data"]["event_id"]
        entry = next(item for item in events.list_event_history()
                     if item.event_id == event_id)
        assert entry.event_type == event_type
        assert entry.tenant_id == "tenant"
        assert entry.payload["idempotency_key"] == payload["idempotency_key"]
    finally:
        _restore(previous)


def test_wrong_tenant_is_rejected(tmp_path) -> None:
    events, native, previous = _composed(tmp_path)
    payload = _reward_payload("reward:wf-1:tenant-probe")  # payload tenant == "tenant"
    binding = _binding(payload, tenant="attacker")
    try:
        structured = _sc(_invoke(native, binding, payload))
        assert structured["ok"] is False
        assert structured["error"] == "learning_signal_tenant_mismatch"
    finally:
        _restore(previous)


def test_wrong_digest_is_rejected(tmp_path) -> None:
    events, native, previous = _composed(tmp_path)
    payload = _reward_payload("reward:wf-1:digest-probe")
    binding = _binding(payload, digest="a" * 64)
    try:
        structured = _sc(_invoke(native, binding, payload))
        assert structured["ok"] is False
        assert structured["error"] == "learning_signal_digest_mismatch"
    finally:
        _restore(previous)


def test_disallowed_event_type_is_rejected(tmp_path) -> None:
    events, native, previous = _composed(tmp_path)
    payload = _reward_payload("reward:wf-1:type-probe")
    binding = _binding(payload, event_type="wallet.rewarded")
    try:
        assert _failed(_invoke(native, binding, payload)) is True
    finally:
        _restore(previous)
