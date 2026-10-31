"""Authenticated HTTP upstream factory for host-side workload proxies."""
from __future__ import annotations

from typing import Any
import os
from urllib.parse import urlsplit

from factory.mcp_utils.interface import (
    CapabilityInvocation, CapabilityScope, HttpScopedCapabilityClient,
)


class _OwnedHTTPUpstream:
    def __init__(self, delegate: HttpScopedCapabilityClient, http_client: Any) -> None:
        self._delegate = delegate
        self._http_client = http_client

    @property
    def scope(self) -> CapabilityScope:
        return self._delegate.scope

    async def list_capabilities(self):
        return await self._delegate.list_capabilities()

    async def invoke(self, request: CapabilityInvocation):
        return await self._delegate.invoke(request)

    async def close(self) -> None:
        try:
            await self._delegate.close()
        finally:
            await self._http_client.aclose()


class AuthenticatedHTTPUpstreamFactory:
    """Create one exact bearer-authenticated MCP upstream per launch."""

    def __init__(self, url: str, *, timeout_seconds: float = 120.0) -> None:
        if not isinstance(url, str) or not url:
            raise ValueError("authenticated MCP upstream URL is required")
        parsed = urlsplit(url)
        local_http = parsed.scheme == "http" \
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"} \
            and os.environ.get("MCP_LOCAL_AUTH", "").lower() in {"1", "true", "yes"}
        if parsed.username or parsed.password or not parsed.hostname \
                or (parsed.scheme != "https" and not local_http):
            raise ValueError("authenticated MCP upstream requires HTTPS")
        self._url = url
        self._timeout = timeout_seconds

    async def __call__(self, access_token: str,
                       scope: CapabilityScope) -> _OwnedHTTPUpstream:
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("workload access token is required")
        import httpx
        http_client = httpx.AsyncClient(headers={
            "Authorization": f"Bearer {access_token}",
        })
        delegate = HttpScopedCapabilityClient(
            self._url, scope, http_client=http_client,
            timeout_seconds=self._timeout,
        )
        owned = _OwnedHTTPUpstream(delegate, http_client)
        try:
            listed = await owned.list_capabilities()
            if {item.name for item in listed} != set(scope.tool_names):
                raise RuntimeError("authenticated upstream did not expose exact scope")
            return owned
        except Exception:
            await owned.close()
            raise


__all__ = ["AuthenticatedHTTPUpstreamFactory"]
