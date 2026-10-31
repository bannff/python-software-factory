"""Thread pool isolation — MCP queries vs agent tool calls.

Two pools prevent graph agents from starving external MCP queries:
- _MCP_POOL: reserved for external MCP protocol operations
- _AGENT_POOL: for graph/swarm calls and trusted nested NativeEnvelopeInvoker
  execution, keeping recursive composition off the external protocol pool

Pool sizes configurable via env vars (no restart needed for new processes).

Both ``_run_sync`` and ``_run_sync_agent`` snapshot the caller's context
(``contextvars.copy_context()``) and execute the awaitable under that
context. This ensures envelope contextvars (session_id, run_id, caller
hint, etc.) propagate from the API loop into the worker thread's fresh
asyncio loop — without it, instrumentation in pool-dispatched tool calls
sees an empty context and emits live events without correlation IDs.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import os
import threading
from typing import Any

_POOL_LOCK = threading.Lock()
_MCP_POOL: concurrent.futures.ThreadPoolExecutor | None = None
_AGENT_POOL: concurrent.futures.ThreadPoolExecutor | None = None

_AGENT_POOL_SIZE = int(os.environ.get("MCP_AGENT_POOL_SIZE", "8"))
_AGENT_SEM = threading.BoundedSemaphore(_AGENT_POOL_SIZE)


def _pool(agent: bool) -> concurrent.futures.ThreadPoolExecutor:
    """Return the requested process pool, recreating it after shutdown."""
    global _MCP_POOL, _AGENT_POOL
    with _POOL_LOCK:
        current = _AGENT_POOL if agent else _MCP_POOL
        if current is None:
            current = concurrent.futures.ThreadPoolExecutor(
                max_workers=_AGENT_POOL_SIZE if agent else int(os.environ.get("MCP_POOL_SIZE", "2")),
                thread_name_prefix="mcp-agent" if agent else "mcp-proto",
            )
            if agent:
                _AGENT_POOL = current
            else:
                _MCP_POOL = current
        return current


def shutdown_pools() -> None:
    """Drain executor workers at a transport lifespan boundary."""
    global _MCP_POOL, _AGENT_POOL
    with _POOL_LOCK:
        pools = (_MCP_POOL, _AGENT_POOL)
        _MCP_POOL = _AGENT_POOL = None
    for pool in pools:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)


def _run_in_ctx(ctx: contextvars.Context, coro: Any) -> Any:
    """Run ``asyncio.run(coro)`` under the given context.

    ``ctx.run`` activates the captured contextvars before ``asyncio.run``
    creates a new event loop, so the loop's tasks inherit the context.
    """
    return ctx.run(asyncio.run, coro)


def _run_sync(result: Any) -> Any:
    """Resolve an awaitable via the MCP protocol pool."""
    if not hasattr(result, "__await__"):
        return result
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        ctx = contextvars.copy_context()
        return _pool(False).submit(_run_in_ctx, ctx, result).result()
    return asyncio.run(result)


def _run_sync_agent(result: Any) -> Any:
    """Resolve an awaitable via the agent pool with backpressure."""
    if not hasattr(result, "__await__"):
        return result
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        ctx = contextvars.copy_context()
        _AGENT_SEM.acquire()
        try:
            return _pool(True).submit(_run_in_ctx, ctx, result).result()
        finally:
            _AGENT_SEM.release()
    return asyncio.run(result)
