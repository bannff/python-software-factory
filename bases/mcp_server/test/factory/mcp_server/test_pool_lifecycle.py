"""Lifecycle regressions for isolated MCP and Agent executor pools."""
from __future__ import annotations

import asyncio

from factory.mcp_server.runtime import pools


async def _dispatch_both() -> tuple[str, str]:
    protocol = pools._run_sync(asyncio.sleep(0, result="protocol"))
    agent = pools._run_sync_agent(asyncio.sleep(0, result="agent"))
    return protocol, agent


def test_shutdown_drains_and_lazily_recreates_both_pools() -> None:
    pools.shutdown_pools()
    assert asyncio.run(_dispatch_both()) == ("protocol", "agent")
    first_protocol = pools._MCP_POOL
    first_agent = pools._AGENT_POOL
    assert first_protocol is not None and first_agent is not None

    pools.shutdown_pools()
    assert pools._MCP_POOL is None and pools._AGENT_POOL is None
    assert first_protocol._shutdown and first_agent._shutdown

    assert asyncio.run(_dispatch_both()) == ("protocol", "agent")
    assert pools._MCP_POOL is not first_protocol
    assert pools._AGENT_POOL is not first_agent
    pools.shutdown_pools()


def test_shutdown_is_idempotent_before_any_dispatch() -> None:
    pools.shutdown_pools()
    pools.shutdown_pools()
    assert pools._MCP_POOL is None and pools._AGENT_POOL is None
