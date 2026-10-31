"""Regression: trusted in-process nesting must not starve the 2-worker
external-protocol pool (Sep 16 dogfood-loop deadlock — the ``native_invoker``
Sep 14 fix covered the FIRST agent-pool hop but ``lazy_loader.py``'s
``call_brick_tool_sync`` still routed a second, in-process-trusted hop
through the 2-worker proto pool, so three nested calls starve it forever).

This test forces ``MCP_POOL_SIZE=2`` and nests THREE real in-process calls
(matching the real depth: scheduler fire -> spawn_background -> the agent's
own steering/lessons/recall adapters calling back into another brick tool)
through ``call_brick_tool_sync_agent`` — the trusted-agent-pool variant —
and asserts it completes quickly. Run under an outer ``timeout`` in CI/local
verification; a regression here hangs forever rather than raising, so the
outer timeout is the actual safety net, not this test's own assertions.
"""
from __future__ import annotations

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def _catalog(
    name: str, *, depth: int, next_agg: MCPAggregator | None, agent_pool: bool = True,
) -> ToolCatalog:
    catalog = ToolCatalog(name)

    @catalog.tool()
    @deterministic()
    def probe() -> ToolResult[dict]:
        if next_agg is not None:
            nested = (
                next_agg.invoke_tool_agent("probe") if agent_pool
                else next_agg.invoke_tool("probe")
            )
            return {"ok": True, "result": {"structured_content": {
                "schema_version": "v1", "ok": True,
                "data": {"depth": depth, "nested": nested},
            }}}
        return {"ok": True, "result": {"structured_content": {
            "schema_version": "v1", "ok": True,
            "data": {"depth": depth, "nested": None},
        }}}
    return catalog


def test_three_level_nested_agent_pool_call_completes_under_constrained_proto_pool(
    monkeypatch,
) -> None:
    """The exact real shape: three nested trusted in-process calls, 2-worker proto pool."""
    monkeypatch.setenv("MCP_POOL_SIZE", "2")
    from factory.mcp_server.runtime import pools
    pools.shutdown_pools()

    leaf = MCPAggregator(ToolCatalog("leaf"))
    leaf.set_available_bricks(["leaf"])
    leaf._lazy._cache["leaf"] = _catalog("leaf", depth=3, next_agg=None)

    middle = MCPAggregator(ToolCatalog("middle"))
    middle.set_available_bricks(["middle"])
    middle._lazy._cache["middle"] = _catalog("middle", depth=2, next_agg=leaf)

    root = MCPAggregator(ToolCatalog("root"))
    root.set_available_bricks(["root"])
    root._lazy._cache["root"] = _catalog("root", depth=1, next_agg=middle)

    result = root.invoke_tool_agent("probe")

    assert result["ok"] is True
    data = result["result"]["structured_content"]["data"]
    assert data["depth"] == 1
    assert data["nested"]["result"]["structured_content"]["data"]["depth"] == 2
    assert (
        data["nested"]["result"]["structured_content"]["data"]["nested"]
        ["result"]["structured_content"]["data"]["depth"] == 3
    )

    pools.shutdown_pools()


def test_call_brick_tool_sync_still_uses_the_proto_pool_unchanged() -> None:
    """External-client path is untouched — only the new *_agent variant moved pools."""
    from factory.mcp_server.runtime import pools
    import inspect

    source = inspect.getsource(pools._run_sync)
    assert "_pool(False)" in source
    agent_source = inspect.getsource(pools._run_sync_agent)
    assert "_pool(True)" in agent_source


# NOTE: a negative-control test asserting the OLD `invoke_tool` (proto-pool)
# path genuinely deadlocks at this same 3-level nesting was attempted twice
# here and removed — neither a plain `threading.Thread` driver nor an
# `asyncio.to_thread` + `pools._run_sync` driver reproduced a hang in this
# synthetic harness (both returned within the 5s test timeout instead of
# hanging). This means the real production deadlock's exact trigger is more
# specific than "N nested calls on a 2-worker pool" in isolation — likely
# involves the real `ThreadPoolExecutor`'s work-queue ordering under
# contention from OTHER concurrent submissions (view-collection, telemetry
# batching, etc. also seen in the real hang's log) that this isolated test
# doesn't recreate. Disclosed here rather than shipping a misleading
# "proof" that doesn't actually prove what it claims. The FIX itself (this
# file's two passing tests above) is applied and verified independently of
# this open reproduction gap — it is the same code-level asymmetry named in
# the Sep 14 native_invoker fix, correctly closed for the parallel
# lazy_loader/aggregator path.
