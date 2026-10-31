"""Structured workflow invoker contracts in progressive and flat modes."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import BaseModel

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    cache_clear, get_envelope, reset_envelope, set_envelope, operational,
)


class _TypedOutput(BaseModel):
    value: int

TARGET = {"brick_name": "demo", "tool_name": "ping"}


def _server():
    seen = []
    mcp = ToolCatalog("demo")

    @mcp.tool(name="demo_ping")
    def ping(value: int) -> dict:
        seen.append(get_envelope())
        return {"value": value, "error": "domain"}

    return mcp, seen


def _registered_flat(child):
    aggregator = MCPAggregator(ToolCatalog("root"))
    module = SimpleNamespace(create_mcp_server=lambda: child)
    with patch(
        "factory.mcp_server.runtime.aggregator.importlib.import_module",
        return_value=module,
    ):
        assert aggregator.register_brick("demo") is True
    return aggregator


def _invoke(aggregator):
    return NativeEnvelopeInvoker(aggregator)(
        TARGET, arguments={"value": 3}, idempotency_key="wfa:v1:key",
        envelope={"tenant_id": "tenant", "principal_id": "principal",
                  "correlation_id": "correlation"},
    )


def test_native_invoker_progressive_preserves_explicit_envelope() -> None:
    mcp, seen = _server()
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = mcp
    result = _invoke(aggregator)
    assert result["ok"] is True
    assert result["result"]["structured_content"] == {"value": 3, "error": "domain"}
    assert seen[0]["tenant_id"] == "tenant"
    assert seen[0]["principal_id"] == "principal"
    assert seen[0]["correlation_id"] == "correlation"
    assert seen[0]["attributes"]["workflow_attempt_id"] == "wfa:v1:key"


def test_native_invoker_flat_uses_same_public_envelope_path() -> None:
    mcp, seen = _server()
    aggregator = _registered_flat(mcp)
    result = _invoke(aggregator)
    assert result["ok"] is True
    assert seen[0]["attributes"]["workflow_attempt_id"] == "wfa:v1:key"
    resolved_mcp, resolved, error = aggregator.resolve_brick_tool("demo", "ping")
    assert resolved_mcp is mcp and resolved == "demo_ping" and error is None


def test_unknown_structured_target_is_transport_failure() -> None:
    mcp, _ = _server()
    result = NativeEnvelopeInvoker(_registered_flat(mcp))(
        {"brick_name": "demo", "tool_name": "missing"}, arguments={},
        idempotency_key="wfa:v1:key", envelope={},
    )
    assert result["ok"] is False
    assert result["error"]["type"] == "ToolNotFoundError"


def test_unknown_flat_brick_rejects_colliding_root_tool() -> None:
    root, seen = _server()
    result = _invoke(MCPAggregator(root))
    assert result["ok"] is False
    assert result["error"]["type"] == "ToolNotFoundError"
    assert seen == []


def test_native_invoker_restores_ambient_context() -> None:
    mcp, _ = _server()
    original = {"attributes": {"request_id": "prior"}}
    token = set_envelope(original)
    try:
        _invoke(_registered_flat(mcp))
        assert get_envelope() == original
    finally:
        reset_envelope(token)


def test_native_invoker_flat_registered_child_avoids_mount_prefix_drift() -> None:
    child, seen = _server()
    aggregator = _registered_flat(child)
    result = _invoke(aggregator)
    assert result["ok"] is True
    assert result["result"]["structured_content"] == {"value": 3, "error": "domain"}
    assert seen[0]["attributes"]["workflow_attempt_id"] == "wfa:v1:key"


def test_native_invoker_ambient_identity_owns_derived_correlation() -> None:
    mcp, seen = _server()
    aggregator = _registered_flat(mcp)
    token = set_envelope({
        "tenant_id": "trusted-tenant", "run_id": "trusted-run",
        "attributes": {"ambient": "yes"},
    })
    try:
        result = NativeEnvelopeInvoker(aggregator)(
            TARGET, arguments={"value": 3}, idempotency_key="ambient-key",
            envelope={
                "tenant_id": "attacker-tenant", "correlation_id": "attacker",
                "attributes": {"explicit": "yes"},
            },
        )
    finally:
        reset_envelope(token)
    assert result["ok"] is True
    assert seen[0]["tenant_id"] == "trusted-tenant"
    assert seen[0]["run_id"] == "trusted-run"
    assert seen[0]["correlation_id"] == "trusted-run"
    assert seen[0]["attributes"] == {
        "explicit": "yes", "ambient": "yes", "workflow_attempt_id": "ambient-key",
    }


def test_native_invoker_conflicting_run_ids_fail_as_transport_error() -> None:
    mcp, seen = _server()
    aggregator = _registered_flat(mcp)
    token = set_envelope({"run_id": "trusted-run"})
    try:
        result = NativeEnvelopeInvoker(aggregator)(
            TARGET, arguments={"value": 3}, idempotency_key="conflict-key",
            envelope={"workflow_run_id": "attacker-run"},
        )
        assert get_envelope() == {"run_id": "trusted-run"}
    finally:
        reset_envelope(token)
    assert result["ok"] is False
    assert result["error"]["type"] == "EnvelopeConflictError"
    assert seen == []


def test_native_invoker_workflow_attempt_key_replays_typed_downstream_once() -> None:
    calls = {"count": 0}
    mcp = ToolCatalog("demo")

    @mcp.tool(name="demo_typed")
    @operational(output_model=_TypedOutput)
    def typed(value: int) -> _TypedOutput:
        calls["count"] += 1
        return _TypedOutput(value=value + calls["count"])

    aggregator = _registered_flat(mcp)
    invoker = NativeEnvelopeInvoker(aggregator)
    cache_clear()
    try:
        first = invoker(
            {"brick_name": "demo", "tool_name": "typed"},
            arguments={"value": 3}, idempotency_key="workflow-attempt-key",
            envelope={"principal_id": "principal", "run_id": "run-1"},
        )
        second = invoker(
            {"brick_name": "demo", "tool_name": "typed"},
            arguments={"value": 3}, idempotency_key="workflow-attempt-key",
            envelope={"principal_id": "principal", "run_id": "run-1"},
        )
    finally:
        cache_clear()
    assert calls["count"] == 1
    assert first["ok"] is True and second["ok"] is True
    assert first["result"]["structured_content"] == second["result"]["structured_content"]


def test_native_invoker_requires_exact_agent_steer_binding() -> None:
    from factory.mcp_utils.interface import ToolResult, ok, service_only
    from pydantic import ConfigDict

    class SteerInput(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        tenant_id: str
        owner_id: str
        session_id: str
        delivery_id: str
        revision: int

    child = ToolCatalog("session")
    effects: list[str] = []

    @child.tool(name="session_acknowledge_steer")
    @service_only(callers={"agent"}, binding="steer")
    @operational(input_model=SteerInput, output_model=_TypedOutput)
    def acknowledge(tenant_id: str, owner_id: str, session_id: str,
                    delivery_id: str, revision: int) -> ToolResult[_TypedOutput]:
        effects.append(delivery_id)
        return ok(_TypedOutput(value=revision))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    values = {"tenant_id": "tenant", "owner_id": "owner",
              "session_id": "session", "delivery_id": "delivery", "revision": 1}
    target = {"brick_name": "session", "tool_name": "acknowledge_steer"}
    invoker = NativeEnvelopeInvoker(aggregator).for_caller("agent")
    accepted = invoker(target, arguments=values, steer=values,
                       idempotency_key="steer:delivery:1", envelope={})
    assert accepted["ok"] is True and effects == ["delivery"]

    denied = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
        target, arguments=values, steer=values,
        idempotency_key="steer:delivery:1", envelope={},
    )
    assert denied["ok"] is False
    partial = invoker(
        target, arguments=values, steer={**values, "revision": 2},
        idempotency_key="steer:delivery:2", envelope={},
    )
    assert partial["ok"] is False and effects == ["delivery"]
