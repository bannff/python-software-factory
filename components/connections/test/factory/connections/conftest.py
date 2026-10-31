"""Shared Connections test rig: runtime + gateway aggregator + owner envelope."""
from __future__ import annotations

import asyncio

import pytest

from factory.connections.runtime.adapters.server_store_sqlite import SqliteServerStore
from factory.connections.runtime.runtime import ConnectionsRuntime
from factory.connections.server import create_tool_catalog
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.external_mount import register_external, unregister_external
from factory.mcp_utils.interface import ToolCatalog, reset_envelope, set_envelope

OWNER = {"tenant_id": "local", "principal_id": "local-operator"}


@pytest.fixture
def stack(tmp_path):
    runtime = ConnectionsRuntime(SqliteServerStore(tmp_path / "c.db"))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["connections"])
    runtime.attach_gateway(
        lambda name, catalog: register_external(aggregator, name, catalog),
        lambda name: unregister_external(aggregator, name),
    )
    catalog = create_tool_catalog(runtime)
    aggregator._lazy._cache["connections"] = catalog
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    return runtime, aggregator, tools


@pytest.fixture
def with_owner():
    def _with_owner(call):
        token = set_envelope(dict(OWNER))
        try:
            return call()
        finally:
            reset_envelope(token)
    return _with_owner


@pytest.fixture
def with_owner():
    def _with_owner(call):
        token = set_envelope(dict(OWNER))
        try:
            return call()
        finally:
            reset_envelope(token)
    return _with_owner
