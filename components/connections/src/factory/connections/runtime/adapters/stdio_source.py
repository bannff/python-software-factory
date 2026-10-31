"""Stdio MCP tool source: one owned session task over ``mcp.client.stdio``.

Sibling of ``HttpScopedCapabilityClient`` for process-backed servers. The SDK
transport + ``ClientSession`` are entered, used, and exited in ONE task; callers
submit operations through a queue. Spawn hygiene: argv list (never a shell
string), explicit cwd, a minimal environment plus ONLY the declared env names
resolved from the API process — the API's own secrets are not inherited.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable

from factory.mcp_utils.interface import (
    CapabilityAccessError, CapabilityDescriptor, CapabilityInvocation, CapabilityResult,
)

_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
_Op = Callable[[Any], Awaitable[Any]]


def child_environment(declared: dict[str, str]) -> dict[str, str]:
    """Minimal base plus declared ``NAME -> SOURCE_ENV_NAME`` resolved values."""
    env = {key: os.environ[key] for key in _KEEP if os.environ.get(key)}
    env.update({"NO_COLOR": "1", "PYTHONUTF8": "1"})
    for name, source in declared.items():
        value = os.environ.get(source)
        if value:
            env[name] = value
    return env


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class StdioToolSource:
    def __init__(
        self, command: str, args: tuple[str, ...], *, cwd: str | None,
        env: dict[str, str], timeout_seconds: float = 120.0,
    ) -> None:
        self._command, self._args, self._cwd, self._env = command, list(args), cwd, env
        self._timeout = timeout_seconds
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        self._ready: asyncio.Event | None = None
        self._start_error: BaseException | None = None
        self._terminal: BaseException | None = None
        self._closed = False

    async def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        async def _op(session: Any) -> tuple[CapabilityDescriptor, ...]:
            listed = await session.list_tools()
            return tuple(CapabilityDescriptor(
                tool.name, getattr(tool, "description", "") or "",
                dict(getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}),
            ) for tool in sorted(listed.tools, key=lambda item: item.name))
        return await self._submit(_op)

    async def invoke(self, request: CapabilityInvocation) -> CapabilityResult:
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
        if self._closed:
            return
        self._closed = True
        task, queue = self._task, self._queue
        self._task = None
        if task is None or queue is None or task.done():
            return
        if task.get_loop() is not asyncio.get_running_loop():
            # Foreign loop: deliver the cancel on ITS loop so the SDK's
            # ``stdio_client`` exit path (``_stop_server_process``) reaps the
            # child. A loop that is already closed cannot run anything; that
            # case only arises in tests that build one loop per call.
            loop = task.get_loop()
            if not loop.is_closed():
                loop.call_soon_threadsafe(task.cancel)
            return
        await queue.put(None)
        try:
            await task
        except Exception:  # noqa: BLE001 - shutdown is best-effort
            pass

    async def _submit(self, op: _Op) -> Any:
        if self._closed:
            raise CapabilityAccessError("tool source is closed")
        if self._task is None or self._task.done():
            # First use, or the previous session ended (process exit, loop
            # teardown): re-dial rather than failing every later call.
            self._queue, self._ready, self._start_error = asyncio.Queue(), asyncio.Event(), None
            self._task = asyncio.get_running_loop().create_task(self._run())
            await self._ready.wait()
            if self._start_error is not None:
                raise self._start_error
        assert self._queue is not None and self._task is not None
        if self._task.done():
            raise self._terminal or CapabilityAccessError("session ended")
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((op, future))
        return await future

    async def _run(self) -> None:
        assert self._ready is not None and self._queue is not None
        terminal: BaseException = CapabilityAccessError("session ended")
        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client
            params = StdioServerParameters(
                command=self._command, args=self._args, env=self._env, cwd=self._cwd,
            )
            async with AsyncExitStack() as stack:
                streams = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
                await asyncio.wait_for(session.initialize(), self._timeout)
                self._ready.set()
                while (item := await self._queue.get()) is not None:
                    op, future = item
                    if future.done():
                        continue
                    try:
                        future.set_result(await asyncio.wait_for(op(session), self._timeout))
                    except Exception as exc:  # noqa: BLE001 - surface to caller
                        future.set_exception(exc)
        except Exception as exc:  # noqa: BLE001 - startup/transport failure
            terminal = exc
            if not self._ready.is_set():
                self._start_error = exc
                self._ready.set()
        finally:
            self._terminal = terminal
            while self._queue is not None and not self._queue.empty():
                item = self._queue.get_nowait()
                if item is not None and not item[1].done():
                    item[1].set_exception(terminal)


__all__ = ["StdioToolSource", "child_environment"]
