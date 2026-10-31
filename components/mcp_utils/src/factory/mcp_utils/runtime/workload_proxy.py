"""Bearer-free native MCP v2 proxy for one sandboxed workload launch."""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from pydantic import TypeAdapter

from .scoped_capabilities import (
    CapabilityDescriptor, CapabilityInvocation, CapabilityResult, CapabilityScope,
    ScopedCapabilityClientPort,
)
from .scoped_capability_client import CapabilityAccessError


class ScopedWorkloadProxy:
    """Freeze one exact scope around an authenticated host-side client."""

    def __init__(self, upstream: ScopedCapabilityClientPort,
                 scope: CapabilityScope) -> None:
        if upstream.scope != scope or not scope.tool_names:
            raise ValueError("upstream client must have the exact non-empty frozen scope")
        self._upstream = upstream
        self._scope = scope
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def scope(self) -> CapabilityScope:
        return self._scope

    async def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        async with self._lock:
            self._ensure_open()
            values = await self._upstream.list_capabilities()
            return tuple(value for value in values if value.name in self._scope.tool_names)

    async def invoke(self, request: CapabilityInvocation) -> CapabilityResult:
        async with self._lock:
            self._ensure_open()
            if request.name not in self._scope.tool_names:
                raise CapabilityAccessError("capability outside frozen workload scope")
            return await self._upstream.invoke(request)

    async def rotate(self, upstream: ScopedCapabilityClientPort) -> None:
        """Replace upstream authority without changing container-visible scope."""
        async with self._lock:
            self._ensure_open()
            if upstream.scope != self._scope:
                await upstream.close()
                raise ValueError("rotated client scope must match frozen workload scope")
            previous, self._upstream = self._upstream, upstream
            await previous.close()

    async def close(self) -> None:
        async with self._lock:
            if not self._closed:
                self._closed = True
                await self._upstream.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise CapabilityAccessError("workload proxy is closed")


def build_workload_proxy_server(proxy: ScopedWorkloadProxy) -> Any:
    """Build a real public-callback MCP v2 server for one frozen proxy."""
    from mcp.server import Server
    from mcp.types import CallToolResult, ContentBlock, ListToolsResult, TextContent, Tool

    content_adapter = TypeAdapter(ContentBlock)

    async def list_tools(_context: Any, _params: Any) -> ListToolsResult:
        descriptors = await proxy.list_capabilities()
        return ListToolsResult(tools=[
            Tool(name=item.name, description=item.description,
                 input_schema=item.input_schema)
            for item in descriptors
        ])

    async def call_tool(_context: Any, params: Any) -> CallToolResult:
        if params.name not in proxy.scope.tool_names:
            return CallToolResult(
                content=[TextContent(type="text", text="capability_denied")],
                isError=True,
            )
        invocation = CapabilityInvocation(
            name=params.name, arguments=dict(params.arguments or {}),
            idempotency_key=_invocation_key(
                proxy.scope.digest, params.name, params.arguments or {}),
        )
        try:
            result = await proxy.invoke(invocation)
        except (CapabilityAccessError, TypeError, ValueError):
            return CallToolResult(
                content=[TextContent(type="text", text="capability_denied")],
                isError=True,
            )
        return CallToolResult(
            content=[content_adapter.validate_python(item) for item in result.content],
            structuredContent=result.structured_content,
            isError=result.is_error,
        )

    return Server(
        "workload-scoped-proxy", on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def build_workload_proxy_app(
    proxy: ScopedWorkloadProxy, *, path: str = "/mcp",
) -> Any:
    """Build bearer-free Streamable HTTP ASGI for mounting on a per-launch UDS."""
    return build_workload_proxy_server(proxy).streamable_http_app(
        streamable_http_path=path, stateless_http=True, host="localhost",
    )


def _invocation_key(scope_digest: str, name: str, arguments: Any) -> str:
    payload = json.dumps(
        {"arguments": arguments, "name": name, "scope_digest": scope_digest},
        sort_keys=True, separators=(",", ":"), default=str,
    ).encode()
    return f"workload-proxy:{hashlib.sha256(payload).hexdigest()}"


__all__ = [
    "ScopedWorkloadProxy", "build_workload_proxy_app",
    "build_workload_proxy_server",
]
