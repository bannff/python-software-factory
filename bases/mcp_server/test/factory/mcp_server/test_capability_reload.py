"""'Reload capabilities' fans out to bricks, Agent registries, and connections."""
from __future__ import annotations

import asyncio

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.capability_reload import reload_capabilities
from factory.mcp_server.runtime.external_mount import register_external
from factory.mcp_server.runtime.native_meta import META_TOOL_NAMES, build_native_meta_catalog
from factory.mcp_utils.interface import ToolCatalog, ToolResult, ok, operational
from pydantic import BaseModel


class Empty(BaseModel):
    pass


class Flag(BaseModel):
    ok: bool


def _brick(name: str, tool: str, succeed: bool) -> ToolCatalog:
    catalog = ToolCatalog(name)

    @catalog.tool(name=tool)
    @operational(input_model=Empty, output_model=Flag)
    async def handler() -> ToolResult[Flag]:
        if not succeed:
            raise RuntimeError("boom")
        return ok(Flag(ok=True))

    return catalog


def test_reload_is_a_registered_meta_tool() -> None:
    assert "reload_capabilities" in META_TOOL_NAMES
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks([])
    names = {tool.name for tool in asyncio.run(build_native_meta_catalog(aggregator).list_tools())}
    assert "reload_capabilities" in names


def test_reload_invalidates_bricks_and_reports_each_part_independently(monkeypatch) -> None:
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["agent", "connections", "graph"])
    fakes = {
        "agent": _brick("agent", "reload_config", True),
        "connections": _brick("connections", "connections_reload", False),
        "graph": ToolCatalog("graph"),
    }
    # Invalidation drops the cache; the next call re-imports the brick. Model
    # that re-import so the fan-out is exercised against fresh catalogs.
    monkeypatch.setattr(
        aggregator._lazy, "ensure_loaded",
        lambda name: aggregator._lazy._cache.setdefault(name, fakes[name]),
    )
    register_external(aggregator, "mcp-echo", ToolCatalog("mcp-echo"))

    outcome = asyncio.run(reload_capabilities(aggregator))

    assert outcome["bricks"] == {"agent": "invalidated", "connections": "invalidated", "graph": "invalidated"}
    assert "mcp-echo" not in outcome["bricks"], "external mounts are remounted by connections, not re-imported"
    assert outcome["agent"] == "reloaded"
    assert outcome["connections"].startswith("error:")
    assert "graph" not in aggregator._lazy._cache, "invalidated catalogs re-import on next use"
