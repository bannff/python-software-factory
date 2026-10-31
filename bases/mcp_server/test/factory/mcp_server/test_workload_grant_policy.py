from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from factory.auth.interface import WorkloadGrant
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.workload_grant_policy import GatewayWorkloadGrantPolicy
from factory.mcp_utils.interface import (
    ToolResult, authoring, deterministic, ok, operational, service_only,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str = "x"


class Output(BaseModel):
    value: str


def _catalog() -> MCPAggregator:
    child = ToolCatalog("demo")

    @child.tool(name="demo.read")
    @deterministic(input_model=Input, output_model=Output)
    def read(value: str = "x") -> ToolResult[Output]:
        return ok(Output(value=value))

    @child.tool(name="demo.write")
    @operational(input_model=Input, output_model=Output)
    def write(value: str = "x") -> ToolResult[Output]:
        return ok(Output(value=value))

    @child.tool(name="demo.authoring.change")
    @authoring(input_model=Input, output_model=Output)
    def change(value: str = "x") -> ToolResult[Output]:
        return ok(Output(value=value))

    @child.tool(name="demo.private")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=Input, output_model=Output)
    def private(value: str = "x") -> ToolResult[Output]:
        return ok(Output(value=value))

    @child.tool(name="get_capabilities")
    @deterministic(input_model=Input, output_model=Output)
    def capabilities(value: str = "x") -> ToolResult[Output]:
        return ok(Output(value=value))

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = child
    return aggregator


def _grant(name: str) -> WorkloadGrant:
    return WorkloadGrant.create(
        launch_id="launch", generation=1, tenant_id="tenant",
        audience="companion-x", allowed_tools=[name],
    )


def test_policy_accepts_only_exact_canonical_public_leaf_categories() -> None:
    policy = GatewayWorkloadGrantPolicy(_catalog())
    for name in ("demo_read", "demo_write"):
        grant = _grant(name)
        assert policy.authorize(
            grant, tenant_id="tenant", audience="companion-x") is grant
    for denied in (
        "demo.read", "demo_private", "demo_get_capabilities", "demo_missing",
    ):
        grant = _grant(denied)
        assert policy.authorize(
            grant, tenant_id="tenant", audience="companion-x") is None
    class Request:
        tenant_id = "tenant"
        audience = "companion-x"
        allowed_tools = ["demo_authoring_change"]
    assert policy.authorize(
        Request(), tenant_id="tenant", audience="companion-x") is None


def test_policy_cannot_widen_and_rejects_wrong_binding() -> None:
    policy = GatewayWorkloadGrantPolicy(
        _catalog(), allowed_tools=frozenset({"demo_read"}))
    assert policy.authorize(
        _grant("demo_write"), tenant_id="tenant", audience="companion-x") is None
    grant = _grant("demo_read")
    assert policy.authorize(
        grant, tenant_id="other", audience="companion-x") is None
    assert policy.authorize(
        grant, tenant_id="tenant", audience="other") is None
