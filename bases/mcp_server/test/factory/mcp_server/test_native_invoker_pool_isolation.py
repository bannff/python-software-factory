"""Regression for nested native invocation executor isolation."""

from __future__ import annotations

from unittest.mock import patch

from factory.mcp_server.runtime import native_invoker
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def test_native_invoker_uses_internal_pool_for_nested_awaits() -> None:
    child = ToolCatalog("demo")

    @child.tool(name="demo_ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = child

    with patch.object(
        native_invoker, "_run_sync_agent",
        wraps=native_invoker._run_sync_agent,
    ) as isolated:
        result = NativeEnvelopeInvoker(aggregator)(
            {"brick_name": "demo", "tool_name": "ping"}, arguments={},
            idempotency_key="nested-proof", envelope={},
        )

    assert result["ok"] is True
    assert isolated.call_count == 2
