"""Unit tests for the HTTP phone-home capability client (fake session, no net)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from factory.mcp_utils.runtime.http_capability_client import HttpScopedCapabilityClient
from factory.mcp_utils.runtime.scoped_capabilities import (
    CapabilityInvocation, CapabilityScope,
)
from factory.mcp_utils.runtime.scoped_capability_client import CapabilityAccessError


class _FakeSession:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=[
            SimpleNamespace(name="memory_store", description="store",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="kb_search", description="search",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="secret_tool", description="nope",
                            input_schema={}),
        ])

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(
            content=[{"type": "text", "text": "ok"}],
            structured_content={"stored": True}, is_error=False,
        )


def _client(names, session):
    scope = CapabilityScope.create("test", names)
    c = HttpScopedCapabilityClient("http://x/mcp/", scope)

    async def _fake_submit(op):  # run the op against the fake session, no network
        return await op(session)

    c._submit = _fake_submit  # type: ignore[assignment]
    return c


@pytest.mark.asyncio
async def test_list_capabilities_filters_by_scope():
    c = _client(["memory_store", "kb_search"], _FakeSession())
    caps = await c.list_capabilities()
    names = {d.name for d in caps}
    assert names == {"memory_store", "kb_search"}  # secret_tool excluded


@pytest.mark.asyncio
async def test_invoke_in_scope_maps_result():
    session = _FakeSession()
    c = _client(["memory_store"], session)
    res = await c.invoke(CapabilityInvocation(
        name="memory_store", arguments={"content": "x"}, idempotency_key="k1"))
    assert res.is_error is False
    assert res.structured_content == {"stored": True}
    assert session.calls == [("memory_store", {"content": "x"})]


@pytest.mark.asyncio
async def test_invoke_out_of_scope_rejected():
    c = _client(["memory_store"], _FakeSession())
    with pytest.raises(CapabilityAccessError):
        await c.invoke(CapabilityInvocation(
            name="secret_tool", arguments={}, idempotency_key="k2"))


@pytest.mark.asyncio
async def test_closed_client_rejects():
    scope = CapabilityScope.create("test", ["memory_store"])
    c = HttpScopedCapabilityClient("http://x/mcp/", scope)
    await c.close()
    with pytest.raises(CapabilityAccessError):
        await c._ensure_running()


@pytest.mark.asyncio
async def test_dead_session_task_fails_fast_not_hangs():
    # A completed session task must surface the terminal error, never enqueue
    # to a dead consumer and await forever.
    scope = CapabilityScope.create("test", ["memory_store"])
    c = HttpScopedCapabilityClient("http://x/mcp/", scope)
    done: asyncio.Future = asyncio.get_running_loop().create_future()
    done.set_result(None)
    c._task = done  # type: ignore[assignment]
    c._terminal_error = CapabilityAccessError("transport dropped")
    with pytest.raises(CapabilityAccessError, match="transport dropped"):
        await c.invoke(CapabilityInvocation(
            name="memory_store", arguments={}, idempotency_key="k5"))


def test_drain_fails_pending_futures():
    import asyncio as _a
    scope = CapabilityScope.create("test", ["x"])
    c = HttpScopedCapabilityClient("http://x/mcp/", scope)
    loop = _a.new_event_loop()
    try:
        c._queue = _a.Queue()
        fut = loop.create_future()
        c._queue.put_nowait((lambda s: None, fut))
        c._drain(CapabilityAccessError("boom"))
        assert fut.done() and isinstance(fut.exception(), CapabilityAccessError)
    finally:
        loop.close()
