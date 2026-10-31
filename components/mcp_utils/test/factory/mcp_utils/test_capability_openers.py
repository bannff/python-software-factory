"""Tests for the UDS capability-client factory and openers."""

from __future__ import annotations

import asyncio

import httpx2
import pytest

from factory.mcp_utils.runtime.capability_openers import (
    build_uds_http_client_factory, open_uds_capability_client,
)
from factory.mcp_utils.runtime.http_capability_client import HttpScopedCapabilityClient


def test_uds_factory_builds_httpx2_client_over_socket() -> None:
    """Factory yields an httpx2 client whose transport is bound to the socket."""
    factory = build_uds_http_client_factory("/run/companion-x/mcp.sock")
    client = factory()
    try:
        assert isinstance(client, httpx2.AsyncClient)
        assert client.follow_redirects is True
        # transport is the UDS transport, not a default TCP pool
        assert isinstance(client._transport, httpx2.AsyncHTTPTransport)
    finally:
        asyncio.run(client.aclose())


def test_uds_factory_returns_fresh_client_each_call() -> None:
    factory = build_uds_http_client_factory("/tmp/x.sock")
    a, b = factory(), factory()
    assert a is not b
    for c in (a, b):
        asyncio.run(c.aclose())


def test_client_stores_http_client_factory() -> None:
    from factory.mcp_utils.runtime.scoped_capabilities import CapabilityScope
    sentinel = build_uds_http_client_factory("/tmp/x.sock")
    client = HttpScopedCapabilityClient(
        "http://localhost:80/mcp", CapabilityScope.create("workload:l", []),
        http_client_factory=sentinel)
    assert client._http_client_factory is sentinel


@pytest.mark.asyncio
async def test_open_uds_fails_closed_on_dead_socket() -> None:
    """No proxy listening ⇒ opener surfaces an error, never hangs/leaks."""
    with pytest.raises(Exception):  # noqa: B017 - transport/connection failure
        await open_uds_capability_client(
            "http://localhost:80/mcp", "/nonexistent/mcp.sock",
            allowlist=["memory_store"], policy_id="workload:test",
            timeout_seconds=5.0)
