from __future__ import annotations

import asyncio

from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.authorization import trusted_arguments
from factory.mcp_utils.interface import (
    AccessDecision, AccessPrincipal, ToolResult, get_service, ok, operational,
    reset_envelope, set_envelope, set_service,
)
from factory.mcp_utils.runtime.tool_catalog import CatalogTool, ToolCatalog


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Output(BaseModel):
    count: int


class Controller:
    def __init__(self, allowed: bool) -> None:
        self.allowed, self.operations = allowed, []

    def principal(self):
        return AccessPrincipal(subject="p", client_id="c")

    def decide(self, _principal, operation):
        self.operations.append(operation)
        return AccessDecision(allowed=self.allowed, reason="policy")


def _aggregator(effects: list[int]) -> MCPAggregator:
    @operational(input_model=Input, output_model=Output)
    def dot_tool() -> ToolResult[Output]:
        effects.append(1)
        return ok(Output(count=len(effects)))

    catalog = ToolCatalog("demo")
    catalog.add_tool(CatalogTool("demo.read", "", dot_tool))
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = catalog
    return aggregator


def test_progressive_discovery_and_execution_share_canonical_policy() -> None:
    effects: list[int] = []
    aggregator = _aggregator(effects)
    controller = Controller(True)
    previous = get_service("mcp_access_controller")
    set_service("mcp_access_controller", controller)
    try:
        discovered = aggregator.get_brick_tools("demo")
        dot = asyncio.run(aggregator.call_public_brick_tool("demo", "demo.read", {}))
        underscore = asyncio.run(aggregator.call_public_brick_tool("demo", "demo_read", {}))
    finally:
        set_service("mcp_access_controller", previous)
    assert discovered["count"] == 1 and dot["ok"] and underscore["ok"]
    executed = [op for op in controller.operations if op.action == "execute"]
    assert len(executed) == 2
    assert {op.public_name for op in executed} == {"demo_read"}
    assert effects == [1, 1]


def test_progressive_denial_happens_before_effect() -> None:
    effects: list[int] = []
    aggregator = _aggregator(effects)
    previous = get_service("mcp_access_controller")
    set_service("mcp_access_controller", Controller(False))
    try:
        discovered = aggregator.get_brick_tools("demo")
        result = asyncio.run(aggregator.call_public_brick_tool("demo", "demo.read", {}))
    finally:
        set_service("mcp_access_controller", previous)
    assert discovered["tools"] == [] and discovered["count"] == 0
    assert result["ok"] is False and result["error"]["message"] == "authorization_denied"
    assert effects == []


def test_progressive_rejects_caller_authority_before_effect() -> None:
    effects: list[int] = []
    aggregator = _aggregator(effects)
    previous = get_service("mcp_access_controller")
    set_service("mcp_access_controller", Controller(True))
    try:
        result = asyncio.run(aggregator.call_public_brick_tool(
            "demo", "demo.read", {"envelope": {"principal_id": "forged"}},
        ))
    finally:
        set_service("mcp_access_controller", previous)
    assert result["ok"] is False
    assert result["error"]["message"] == "authorization_denied"
    assert effects == []




class StrictEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    producer_id: str | None = None
    visibility: str | None = None
    source_namespace: str | None = None
    agent_id: str | None = None


class EnvelopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    envelope: StrictEnvelope | None = None


def test_trusted_arguments_projects_strict_envelope_and_preserves_session() -> None:
    @operational(input_model=EnvelopeInput, output_model=Output)
    def tool(envelope: StrictEnvelope | None = None) -> ToolResult[Output]:
        assert envelope is not None
        return ok(Output(count=1))

    catalog_tool = CatalogTool("demo.envelope", "", tool)
    token = set_envelope({
        "tenant_id": "ambient-tenant", "principal_id": "ambient-owner",
        "session_id": None, "tool_name": "call_brick_tool",
        "attributes": {"client_id": "local"},
    })
    try:
        trusted = trusted_arguments(catalog_tool, {"envelope": {
            "tenant_id": "forged", "principal_id": "forged",
            "session_id": "active-session", "producer_id": "forged",
            "visibility": "public", "source_namespace": "forged",
            "agent_id": "forged",
        }})
    finally:
        reset_envelope(token)
    assert trusted == {"envelope": {
        "tenant_id": "ambient-tenant", "principal_id": "ambient-owner",
        "session_id": "active-session",
    }}
    assert tool(**trusted).ok


def test_trusted_arguments_prefers_non_null_ambient_session() -> None:
    @operational(input_model=EnvelopeInput, output_model=Output)
    def tool(envelope: StrictEnvelope | None = None) -> ToolResult[Output]:
        return ok(Output(count=1))

    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "ambient-session", "tool_name": "call_brick_tool",
    })
    try:
        trusted = trusted_arguments(
            CatalogTool("demo.envelope", "", tool),
            {"envelope": {"session_id": "forged-session"}},
        )
    finally:
        reset_envelope(token)
    assert trusted == {"envelope": {
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "ambient-session",
    }}


def test_progressive_resources_and_prompts_require_target_policy() -> None:
    aggregator = _aggregator([])
    controller = Controller(False)
    previous = get_service("mcp_access_controller")
    set_service("mcp_access_controller", controller)
    try:
        resources = aggregator.get_brick_resources("demo")
        prompts = aggregator.get_brick_prompts("demo")
        read = asyncio.run(aggregator.read_brick_resource("demo", "demo://secret"))
        render = asyncio.run(aggregator.render_brick_prompt("demo", "secret"))
    finally:
        set_service("mcp_access_controller", previous)
    assert resources["count"] == prompts["count"] == 0
    assert read == render == {"error": "authorization_denied"}
    assert {(op.category, op.action) for op in controller.operations} == {
        ("resource", "discover"), ("prompt", "discover"),
        ("resource", "execute"), ("prompt", "execute"),
    }
