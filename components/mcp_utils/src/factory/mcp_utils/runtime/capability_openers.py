"""Openers for the scoped Streamable-HTTP / UDS capability client.

Thin conveniences over ``HttpScopedCapabilityClient``: open a session, discover
the remote tool surface, and return a client scoped to an exact allowlist.

The UDS variant is the squad workload path: the trusted host bind-mounts a
per-launch Unix socket into the container and injects only ``MCP_PROXY_SOCKET``
+ ``MCP_PROXY_URL`` + ``MCP_POLICY_ID`` — no bearer, no token. The client dials
the mounted socket via an ``httpx2.AsyncHTTPTransport(uds=...)`` (the MCP SDK's
Streamable-HTTP transport is typed on ``httpx2``, NOT stdlib ``httpx``), so no
TCP connection is opened. Credential issuance and transparent rotation are
entirely host-owned; the container does nothing.
"""
from __future__ import annotations

from typing import Any, Callable

from .http_capability_client import HttpScopedCapabilityClient
from .scoped_capabilities import CapabilityScope

_DEFAULT_POLICY = "squad-phone-home"


def build_uds_http_client_factory(socket_path: str) -> Callable[[], Any]:
    """Return a zero-arg factory that builds an MCP-configured httpx2 client
    bound to a Unix socket (no TCP), mirroring the SDK's client defaults."""
    def _factory() -> Any:
        import httpx2
        return httpx2.AsyncClient(
            transport=httpx2.AsyncHTTPTransport(uds=socket_path),
            follow_redirects=True,
            timeout=httpx2.Timeout(30.0, read=300.0),
        )
    return _factory


async def _scoped(
    client: HttpScopedCapabilityClient, allowlist: list[str] | None, policy_id: str,
) -> HttpScopedCapabilityClient:
    async def _list_all(session: Any) -> list[str]:
        listed = await session.list_tools()
        return [tool.name for tool in listed.tools]

    discovered = await client._submit(_list_all)
    names = list(allowlist) if allowlist is not None else discovered
    client._scope = CapabilityScope.create(policy_id, names)
    return client


async def open_http_capability_client(
    url: str, *, allowlist: list[str] | None = None, http_client: Any | None = None,
    policy_id: str = _DEFAULT_POLICY, timeout_seconds: float = 120.0,
) -> HttpScopedCapabilityClient:
    """Open a TCP Streamable-HTTP session and return a scoped client.

    ``allowlist=None`` scopes to ALL discovered tools (the squad 'employee'
    default); an explicit list narrows the remote surface.
    """
    client = HttpScopedCapabilityClient(
        url, CapabilityScope.create(policy_id, []),
        http_client=http_client, timeout_seconds=timeout_seconds)
    return await _scoped(client, allowlist, policy_id)


async def open_uds_capability_client(
    url: str, socket_path: str, *, allowlist: list[str] | None = None,
    policy_id: str = _DEFAULT_POLICY, timeout_seconds: float = 120.0,
) -> HttpScopedCapabilityClient:
    """Open a Streamable-HTTP session over a mounted Unix socket (no TCP, no
    bearer) and return a client scoped to ``allowlist``."""
    client = HttpScopedCapabilityClient(
        url, CapabilityScope.create(policy_id, []),
        http_client_factory=build_uds_http_client_factory(socket_path),
        timeout_seconds=timeout_seconds)
    return await _scoped(client, allowlist, policy_id)


__all__ = [
    "build_uds_http_client_factory", "open_http_capability_client",
    "open_uds_capability_client",
]
