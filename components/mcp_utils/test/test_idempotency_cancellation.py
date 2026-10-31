"""Cancellation regressions for typed single-flight idempotency."""
from __future__ import annotations

import asyncio
from typing import Literal

import pytest
from pydantic import BaseModel

from factory.mcp_utils.runtime import idempotency
from factory.mcp_utils.context import reset_envelope, set_envelope
from factory.mcp_utils.decorators import operational
from factory.mcp_utils.runtime.idempotency import cache_clear
from factory.mcp_utils.runtime.schema_migration import clear_steps
from factory.mcp_utils.runtime.tool_result import ToolResult


class _In(BaseModel):
    schema_version: Literal["v1"] = "v1"
    value: int = 0
    idempotency_key: str | None = None


class _Out(BaseModel):
    schema_version: Literal["v1"] = "v1"
    value: int


@pytest.fixture(autouse=True)
def _clean() -> None:
    token = set_envelope({"principal_id": "cancel-test"})
    cache_clear()
    clear_steps()
    yield
    cache_clear()
    clear_steps()
    reset_envelope(token)


@pytest.mark.asyncio
async def test_cancelled_owner_releases_waiters_and_allows_retry() -> None:
    started = asyncio.Event()
    waiter_entered = asyncio.Event()
    calls = 0

    @operational(input_model=_In, output_model=_Out)
    async def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        nonlocal calls
        calls += 1
        started.set()
        if calls == 1:
            await asyncio.sleep(60)
        return _Out(value=value)

    loop = asyncio.get_running_loop()
    original_wait_for = idempotency.wait_for

    def mark_wait(flight):
        loop.call_soon_threadsafe(waiter_entered.set)
        return original_wait_for(flight)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(idempotency, "wait_for", mark_wait)
        owner = asyncio.create_task(tool(value=1, idempotency_key="cancel-key"))
        await asyncio.wait_for(started.wait(), timeout=1)
        waiter = asyncio.create_task(tool(value=1, idempotency_key="cancel-key"))
        await asyncio.wait_for(waiter_entered.wait(), timeout=1)
        assert not waiter.done()

        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner

        waited = await asyncio.wait_for(waiter, timeout=1)
        assert isinstance(waited, ToolResult)
        assert waited.ok is False
        assert waited.error == "tool_execution_failed"
        assert waited.idempotency_key == "cancel-key"

        retry = await asyncio.wait_for(
            tool(value=1, idempotency_key="cancel-key"), timeout=1,
        )
    assert isinstance(retry, ToolResult)
    assert retry.ok is True
    assert retry.data is not None and retry.data.value == 1
    assert calls == 2


def test_cache_clear_waiter_failure_retains_idempotency_key() -> None:
    identity = idempotency.ReplayIdentity("scope", "clear-key", "ctx", "input")
    decision = idempotency.lookup_or_claim(identity)
    assert decision.flight is not None
    cache_clear()
    result = idempotency.wait_for(decision.flight)
    assert result.error == "tool_execution_failed"
    assert result.idempotency_key == "clear-key"
