"""HTTP MCP server registration tests."""
from __future__ import annotations

import asyncio

from factory.http.server import create_mcp_server


class Runtime:
    def health_check(self): return {}


def test_contract_tools_return_typed_envelopes() -> None:
    mcp = create_mcp_server(Runtime())
    caps = asyncio.run(mcp.get_tool("http_get_capabilities")).fn()
    health = asyncio.run(mcp.get_tool("http_health_check")).fn()
    schema = asyncio.run(mcp.get_tool("http_describe_config_schema")).fn()
    assert caps.ok and caps.data.name == "http"
    assert health.ok and health.data.status == "healthy"
    assert schema.ok and schema.data.client_config.properties["backend"].enum == ["httpx", "aiohttp"]
