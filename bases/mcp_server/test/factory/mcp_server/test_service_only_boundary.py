"""End-to-end service-only catalog, dispatch, and claims contracts."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from pydantic import BaseModel, ConfigDict

from factory.mcp_server import interface as mcp_interface
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_server.runtime.tool_catalog import build_tool_catalog
from factory.mcp_utils.interface import (
    AttemptBinding, ToolResult, get_internal_invocation_claims,
    mint_internal_invocation_claims, ok, operational,
    reset_internal_invocation_claims, service_only, set_internal_invocation_claims,
)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str
    value: int = 1


class _Output(BaseModel):
    changed: bool


class _PublicInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _PublicOutput(BaseModel):
    public: bool


def _fixture():
    effects: list[int] = []
    child = ToolCatalog("demo")

    @child.tool(name="demo_public")
    @operational(input_model=_PublicInput, output_model=_PublicOutput)
    def public() -> ToolResult[_PublicOutput]:
        return ok(_PublicOutput(public=True))

    @child.tool(name="demo_protected")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_Input, output_model=_Output)
    def protected(
        workflow_run_id: str, attempt_id: str, revision: int,
        manifest_digest: str, value: int = 1,
    ) -> ToolResult[_Output]:
        effects.append(value)
        return ok(_Output(changed=True))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = child
    return aggregator, effects


def _arguments() -> dict:
    return {
        "workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 2,
        "manifest_digest": "a" * 64, "value": 7,
    }


def _binding(**updates) -> AttemptBinding:
    values = {
        "workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 2,
        "manifest_digest": "a" * 64,
    }
    values.update(updates)
    return AttemptBinding(**values)


def _tool(aggregator):
    child, resolved, error = aggregator.resolve_brick_tool("demo", "protected")
    assert child is not None and resolved is not None and error is None
    return asyncio.run(child.get_tool(resolved))


def _claims(aggregator, **updates):
    values = {
        "caller": "workflow", "audience": "demo", "target_tool": "demo_protected",
        "binding": _binding(), "target": _tool(aggregator),
    }
    values.update(updates)
    return mint_internal_invocation_claims(**values)


def _call_with_claims(aggregator, claims, arguments=None):
    token = set_internal_invocation_claims(claims)
    try:
        return asyncio.run(aggregator.call_brick_tool(
            "demo", "protected", arguments or _arguments(),
        ))
    finally:
        reset_internal_invocation_claims(token)


def test_caller_bound_native_invocation_is_authorized_and_restores_claims() -> None:
    aggregator, effects = _fixture()
    prior = _claims(aggregator, target_tool="prior")
    token = set_internal_invocation_claims(prior)
    try:
        result = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
            {"brick_name": "demo", "tool_name": "protected"},
            arguments=_arguments(), idempotency_key="attempt-1",
            envelope={"run_id": "run-1"},
            attempt={
                "workflow_run_id": "run-1", "attempt_id": "attempt-1",
                "revision": 2, "manifest_digest": "a" * 64,
            },
        )
        assert get_internal_invocation_claims() is prior
    finally:
        reset_internal_invocation_claims(token)
    assert result["ok"] is True
    assert effects == [7]


@pytest.mark.parametrize("change", [
    {"caller": "attacker"}, {"audience": "other"},
    {"target_tool": "demo_public"}, {"binding": _binding(workflow_run_id="run-2")},
    {"binding": _binding(attempt_id="attempt-2")}, {"binding": _binding(revision=3)},
    {"binding": _binding(manifest_digest="b" * 64)},
])
def test_wrong_claim_is_rejected_before_side_effects(change) -> None:
    aggregator, effects = _fixture()
    result = _call_with_claims(aggregator, _claims(aggregator, **change))
    assert result["ok"] is False
    assert result["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []


def test_absent_or_forged_public_claims_are_denied() -> None:
    aggregator, effects = _fixture()
    forged = {**_arguments(), "caller": "workflow", "audience": "demo"}
    result = asyncio.run(aggregator.call_brick_tool("demo", "protected", forged))
    assert result["ok"] is False
    unbound = NativeEnvelopeInvoker(aggregator)(
        {"brick_name": "demo", "tool_name": "protected"},
        arguments=_arguments(), idempotency_key="attempt-1",
        envelope={"run_id": "run-1", "attributes": {"caller": "workflow"}},
        attempt={
            "workflow_run_id": "run-1", "attempt_id": "attempt-1",
            "revision": 2, "manifest_digest": "a" * 64,
        },
    )
    assert unbound["error"]["type"] == "ServiceOnlyAccessError"
    assert effects == []


def test_protected_tool_is_absent_from_every_public_server_surface() -> None:
    aggregator, effects = _fixture()
    discovered = aggregator.get_brick_tools("demo")
    assert [tool["name"] for tool in discovered["tools"]] == ["demo_public"]
    assert aggregator.get_brick_tool_names("demo") == ["demo_public"]
    assert aggregator.get_all_tool_names() == ["demo_public"]
    assert build_tool_catalog(aggregator, None)["count"] == 1
    assert "claims are required" in aggregator.invoke_tool("demo_protected")["error"]
    missing = asyncio.run(aggregator.call_brick_tool("demo", "missing", {}))
    assert "demo_protected" not in missing["error"]["message"]

    assert effects == []


def test_claims_are_single_use_within_their_context_scope() -> None:
    aggregator, effects = _fixture()
    token = set_internal_invocation_claims(_claims(aggregator))
    try:
        first = asyncio.run(aggregator.call_brick_tool("demo", "protected", _arguments()))
        second = asyncio.run(aggregator.call_brick_tool("demo", "protected", _arguments()))
    finally:
        reset_internal_invocation_claims(token)
    assert first["ok"] is True
    assert second["ok"] is False
    assert "consumed" in second["error"]["message"]
    assert effects == [7]
