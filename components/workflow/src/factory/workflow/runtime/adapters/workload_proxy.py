"""Production host-side activation for bearer-free workload MCP proxies."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from factory.mcp_utils.interface import (
    CapabilityScope, ScopedCapabilityClientPort, ScopedWorkloadProxy,
    build_workload_proxy_app,
)

from ..workload_lifecycle import WorkloadLaunchManifest

AuthenticatedUpstreamFactory = Callable[
    [str, CapabilityScope], Awaitable[ScopedCapabilityClientPort]
]


class WorkloadProxyHostPort(Protocol):
    async def mount(self, app: Any, *, launch_id: str) -> str: ...
    async def unmount(self, endpoint: str) -> None: ...


class WorkloadProxyActivator:
    """Compose exact authenticated upstream, proxy, app, and host endpoint."""

    def __init__(self, upstream_factory: AuthenticatedUpstreamFactory,
                 host: WorkloadProxyHostPort) -> None:
        self._upstream_factory = upstream_factory
        self._host = host
        self._proxies: dict[str, ScopedWorkloadProxy] = {}
        self._lock = asyncio.Lock()

    async def activate(self, manifest: WorkloadLaunchManifest,
                       access_token: str) -> str:
        grant = manifest.validated_grant()
        scope = CapabilityScope.create(
            grant.policy_id, grant.allowed_tools,
            digest=grant.capability_scope_digest,
        )
        upstream = await self._upstream_factory(access_token, scope)
        if upstream.scope != scope:
            await upstream.close()
            raise ValueError("authenticated upstream returned a different scope")
        proxy = ScopedWorkloadProxy(upstream, scope)
        try:
            endpoint = await self._host.mount(
                build_workload_proxy_app(proxy), launch_id=grant.launch_id)
        except Exception:
            await proxy.close()
            raise
        async with self._lock:
            if endpoint in self._proxies:
                await self._host.unmount(endpoint)
                await proxy.close()
                raise RuntimeError("proxy host returned a duplicate endpoint")
            self._proxies[endpoint] = proxy
        return endpoint

    async def deactivate(self, endpoint: str) -> None:
        async with self._lock:
            proxy = self._proxies.pop(endpoint, None)
        try:
            if proxy is not None:
                await proxy.close()
        finally:
            await self._host.unmount(endpoint)


__all__ = [
    "AuthenticatedUpstreamFactory", "WorkloadProxyActivator",
    "WorkloadProxyHostPort",
]
