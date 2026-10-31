"""#87: a keyless cross-brick call must not stamp workflow_attempt_id=None."""
from __future__ import annotations

from unittest.mock import patch

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

TARGET = {"brick_name": "demo", "tool_name": "ping"}


def _registered_flat(mcp):
    aggregator = MCPAggregator(ToolCatalog("root"))
    module = __import__("types").SimpleNamespace(create_mcp_server=lambda: mcp)
    with patch(
        "factory.mcp_server.runtime.aggregator.importlib.import_module",
        return_value=module,
    ):
        assert aggregator.register_brick("demo") is True
    return aggregator


def test_omits_stamp_when_idempotency_key_is_none() -> None:
    """The workflow Envelope.attributes validator only accepts
    str|int|float|bool, so stamping the literal None made every None-key
    call (agent.list_background_runs → workflow.list_runs, the Subagents
    widget's poll) fail the target tool's envelope validation with
    tool_execution_failed. A keyless call carries no attempt correlation —
    omit the stamp entirely."""
    seen: list = []
    mcp = ToolCatalog("demo")

    @mcp.tool(name="demo_ping")
    def ping(value: int) -> dict:
        from factory.mcp_utils.interface import get_envelope
        seen.append(get_envelope())
        return {"value": value}

    result = NativeEnvelopeInvoker(_registered_flat(mcp))(
        TARGET, arguments={"value": 3}, idempotency_key=None, envelope={},
    )
    assert result["ok"] is True
    assert "workflow_attempt_id" not in seen[0]["attributes"]
