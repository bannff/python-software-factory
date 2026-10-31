"""Internal native invocations project envelopes before strict child ingress."""
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ToolResult, ok, operational
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NarrowEnvelope(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    thread_id: str | None = None


class Input(DTO):
    value: str
    envelope: NarrowEnvelope | None = None


class Output(DTO):
    accepted: bool


def test_internal_invoker_projects_full_envelope_to_child_shape() -> None:
    seen = []
    child = ToolCatalog("scheduler")

    @child.tool(name="scheduler_add")
    @operational(input_model=Input, output_model=Output)
    def add(value: str, envelope: dict | None = None) -> ToolResult[Output]:
        seen.append(envelope)
        return ok(Output(accepted=value == "ok"))

    aggregator = MCPAggregator(ToolCatalog("root"))
    module = SimpleNamespace(create_mcp_server=lambda: child)
    with patch(
        "factory.mcp_server.runtime.aggregator.importlib.import_module",
        return_value=module,
    ):
        assert aggregator.register_brick("scheduler") is True

    result = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
        {"brick_name": "scheduler", "tool_name": "scheduler_add"},
        arguments={"value": "ok", "envelope": {
            "tenant_id": "tenant", "principal_id": "owner",
            "session_id": "thread", "thread_id": "thread",
            "correlation_id": "drop", "agent_id": "drop",
        }},
        idempotency_key="workflow-loop-schedule:test:1",
        envelope={
            "tenant_id": "tenant", "principal_id": "owner",
            "session_id": "thread", "thread_id": "thread",
            "correlation_id": "trusted-correlation", "agent_id": "developer",
        },
    )
    assert result["ok"] is True
    assert seen == [{
        "tenant_id": "tenant", "principal_id": "owner",
        "session_id": "thread", "thread_id": "thread",
    }]
