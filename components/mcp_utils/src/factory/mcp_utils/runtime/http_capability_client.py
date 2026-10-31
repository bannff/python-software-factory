"""HTTP/UDS Streamable transport for the scoped MCP capability port.

Dials a REMOTE MCP endpoint (TCP, or a mounted Unix socket via an
``http_client_factory`` — see ``uds_transport``) so a squad in a separate
container phones home to Companion-X's shared tools. The SDK transport +
``ClientSession`` must be entered/used/exited in ONE anyio task, but a squad's
LangGraph nodes call tools from concurrent tasks — so a dedicated session task +
request queue (an "actor") owns the session; ``close()`` stops it. The factory
is entered inside that task so all connection lifecycle stays single-task.
"""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from copy import deepcopy
from typing import Any, Awaitable, Callable

from .scoped_capabilities import (
    CapabilityDescriptor,
    CapabilityInvocation,
    CapabilityResult,
    CapabilityScope,
)
from .scoped_capability_client import CapabilityAccessError

_Op = Callable[[Any], Awaitable[Any]]


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _open_transport(url: str, http_client: Any | None) -> Any:
    from mcp.client.streamable_http import streamable_http_client
    if http_client is not None:
        return streamable_http_client(url, http_client=http_client)
    return streamable_http_client(url)


class HttpScopedCapabilityClient:
    """Scope a remote Streamable-HTTP MCP server behind the capability port."""

    def __init__(
        self, url: str, scope: CapabilityScope, *,
        http_client: Any | None = None,
        http_client_factory: Callable[[], Any] | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._url = url
        self._scope = scope
        self._http_client = http_client
        self._http_client_factory = http_client_factory
        self._timeout = timeout_seconds
        self._queue: asyncio.Queue[tuple[_Op, asyncio.Future] | None] | None = None
        self._task: asyncio.Task | None = None
        self._ready: asyncio.Event | None = None
        self._start_error: BaseException | None = None
        self._terminal_error: BaseException | None = None
        self._closed = False

    @property
    def scope(self) -> CapabilityScope:
        return self._scope

    async def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        async def _op(session: Any) -> tuple[CapabilityDescriptor, ...]:
            listed = await session.list_tools()
            return tuple(
                CapabilityDescriptor(
                    tool.name, getattr(tool, "description", "") or "",
                    deepcopy(getattr(tool, "input_schema", None) or {}))
                for tool in sorted(listed.tools, key=lambda item: item.name)
                if tool.name in self._scope.tool_names
            )
        return await self._submit(_op)

    async def invoke(self, request: CapabilityInvocation) -> CapabilityResult:
        if request.name not in self._scope.tool_names:
            raise CapabilityAccessError(f"capability outside scope: {request.name}")

        async def _op(session: Any) -> CapabilityResult:
            result = await session.call_tool(request.name, request.arguments)
            structured = getattr(result, "structured_content", None)
            return CapabilityResult(
                content=tuple(_plain(i) for i in getattr(result, "content", ()) or ()),
                structured_content=None if structured is None else _plain(structured),
                is_error=bool(getattr(result, "is_error", False)),
            )
        return await self._submit(_op)

    async def close(self) -> None:
        """Signal the session task to exit and await it, idempotently."""
        if self._closed:
            return
        self._closed = True
        if self._task is not None and self._queue is not None:
            await self._queue.put(None)
            try:
                await self._task
            except Exception:  # noqa: BLE001 - shutdown is best-effort
                pass
        self._task = None

    async def _submit(self, op: _Op) -> Any:
        await self._ensure_running()
        assert self._queue is not None and self._task is not None
        if self._task.done():  # session died between ensure and submit
            raise self._terminal_error or CapabilityAccessError("session ended")
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((op, future))
        return await future

    async def _ensure_running(self) -> None:
        if self._closed:
            raise CapabilityAccessError("capability client is closed")
        if self._task is not None and self._task.done():
            raise self._terminal_error or CapabilityAccessError("session ended")
        if self._task is None:
            self._queue = asyncio.Queue()
            self._ready = asyncio.Event()
            self._start_error = None
            self._task = asyncio.create_task(self._run())
            await self._ready.wait()
            if self._start_error is not None:
                raise self._start_error

    async def _run(self) -> None:
        assert self._ready is not None and self._queue is not None
        terminal: BaseException = CapabilityAccessError("session ended")
        try:
            from mcp import ClientSession
            async with AsyncExitStack() as stack:
                http_client = self._http_client
                if self._http_client_factory is not None:
                    http_client = await stack.enter_async_context(
                        self._http_client_factory())
                streams = await stack.enter_async_context(
                    _open_transport(self._url, http_client))
                session = await stack.enter_async_context(
                    ClientSession(streams[0], streams[1]))
                await session.initialize()
                self._ready.set()
                while True:
                    item = await self._queue.get()
                    if item is None:
                        break
                    op, future = item
                    if future.done():
                        continue
                    try:
                        future.set_result(
                            await asyncio.wait_for(op(session), self._timeout))
                    except Exception as exc:  # noqa: BLE001 - surface to caller
                        future.set_exception(exc)
        except Exception as exc:  # noqa: BLE001 - startup/transport failure
            terminal = exc
            if self._ready is not None and not self._ready.is_set():
                self._start_error = exc
                self._ready.set()
        finally:
            self._terminal_error = terminal
            self._drain(terminal)

    def _drain(self, exc: BaseException) -> None:
        """Fail every still-pending future so no caller hangs on a dead task."""
        if self._queue is None:
            return
        while not self._queue.empty():
            item = self._queue.get_nowait()
            if item is None:
                continue
            _op, future = item
            if not future.done():
                future.set_exception(exc)


__all__ = ["HttpScopedCapabilityClient"]
