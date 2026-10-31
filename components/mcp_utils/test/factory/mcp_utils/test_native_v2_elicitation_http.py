"""Modern Streamable-HTTP canary for elicitation-only MRTR."""

from __future__ import annotations

import httpx
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import ElicitResult

from .mrtr_harness import mrtr_surface


@pytest.mark.asyncio
async def test_modern_http_auto_negotiation_completes_one_elicitation_round() -> None:
    calls: list[int] = []
    server, _ = mrtr_surface(calls)
    manager = StreamableHTTPSessionManager(server, stateless=True)
    transport = httpx.ASGITransport(app=manager.handle_request)

    async with manager.run(), httpx.AsyncClient(
        transport=transport, base_url="http://canary",
    ) as http_client:
        async def accept(_context, _params) -> ElicitResult:
            return ElicitResult(action="accept", content={"approved": True})

        connection = streamable_http_client(
            "http://canary/mcp", http_client=http_client,
        )
        async with Client(
            connection, mode="auto", elicitation_callback=accept,
            input_required_max_rounds=1,
        ) as client:
            result = await client.call_tool("effect", {"value": 9})
            discover = client.session.discover_result

    assert discover is not None
    assert "2026-07-28" in discover.supported_versions
    assert result.structured_content["data"] == {"value": 9}
    assert calls == [9]

@pytest.mark.asyncio
async def test_legacy_http_fails_interactive_tool_cleanly_without_effect() -> None:
    calls: list[int] = []
    server, _ = mrtr_surface(calls)
    manager = StreamableHTTPSessionManager(server, stateless=True)
    transport = httpx.ASGITransport(app=manager.handle_request)

    async with manager.run(), httpx.AsyncClient(
        transport=transport, base_url="http://canary",
    ) as http_client:
        connection = streamable_http_client(
            "http://canary/mcp", http_client=http_client,
        )
        async with Client(connection, mode="legacy") as client:
            result = await client.call_tool("effect", {"value": 9})

    assert result.is_error is True
    assert result.structured_content["error"] == (
        "elicitation requires MCP protocol 2026-07-28"
    )
    assert calls == []
