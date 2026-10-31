"""Streamable-HTTP tool source reusing ``HttpScopedCapabilityClient``.

The scoped client needs the tool names up front, so one short discovery
session lists them first; the long-lived scoped client then owns the session.
Headers map ``Header-Name -> SOURCE_ENV_NAME`` and are resolved from the API
process environment only when the httpx client is built inside the session task.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from factory.mcp_utils.interface import (
    CapabilityDescriptor, CapabilityScope, HttpScopedCapabilityClient,
)


def resolve_headers(declared: dict[str, str]) -> dict[str, str]:
    """Resolve declared header env-name references; unset sources are skipped."""
    return {
        name: os.environ[source]
        for name, source in declared.items() if os.environ.get(source)
    }


async def discover_tools(
    url: str, headers: dict[str, str], *, timeout_seconds: float = 30.0,
) -> tuple[CapabilityDescriptor, ...]:
    """One-shot ``list_tools`` over a fresh session; nothing is retained."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with httpx.AsyncClient(headers=headers, timeout=timeout_seconds) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                listed = await session.list_tools()
    return tuple(CapabilityDescriptor(
        tool.name, getattr(tool, "description", "") or "",
        dict(getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}),
    ) for tool in sorted(listed.tools, key=lambda item: item.name))


def http_source(
    server_name: str, url: str, headers: dict[str, str],
    tool_names: tuple[str, ...], *, timeout_seconds: float = 120.0,
) -> Any:
    """Build the long-lived scoped client for one registered HTTP server."""
    scope = CapabilityScope.create(f"connections:{server_name}", tool_names)
    return HttpScopedCapabilityClient(
        url, scope,
        http_client_factory=lambda: httpx.AsyncClient(
            headers=resolve_headers(headers), timeout=timeout_seconds,
        ),
        timeout_seconds=timeout_seconds,
    )


__all__ = ["discover_tools", "http_source", "resolve_headers"]
