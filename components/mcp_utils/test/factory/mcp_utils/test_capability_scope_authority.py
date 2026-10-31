"""Trusted capability-scope digest and async-context invariants."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_utils.interface import (
    bind_capability_scope, CapabilityScope, get_capability_scope,
    reset_capability_scope,
)
from factory.mcp_utils.runtime.scoped_capability_client import (
    InMemoryScopedCapabilityClient,
)


def test_scope_digest_is_canonical_and_tampering_is_rejected() -> None:
    first = CapabilityScope.create("policy", ["b", "a"], delegation_depth=1)
    second = CapabilityScope.create("policy", ["a", "b"], delegation_depth=1)
    assert first == second
    with pytest.raises(ValueError, match="digest mismatch"):
        CapabilityScope.create(
            "policy", first.tool_names, delegation_depth=1, digest="0" * 64,
        )
    forged = CapabilityScope("policy", "0" * 64, frozenset({"a"}), 1)
    with pytest.raises(ValueError, match="digest mismatch"):
        InMemoryScopedCapabilityClient(forged, (), {})


@pytest.mark.asyncio
async def test_context_resets_after_success_and_exception() -> None:
    outer = CapabilityScope.create("outer", {"a"})
    inner = CapabilityScope.create("inner", {"b"}, delegation_depth=1)
    outer_token = bind_capability_scope(outer)
    try:
        token = bind_capability_scope(inner)
        try:
            assert get_capability_scope() is inner
        finally:
            reset_capability_scope(token)
        assert get_capability_scope() is outer
        token = bind_capability_scope(inner)
        with pytest.raises(RuntimeError):
            try:
                raise RuntimeError("boom")
            finally:
                reset_capability_scope(token)
        assert get_capability_scope() is outer
    finally:
        reset_capability_scope(outer_token)
    assert get_capability_scope() is None


@pytest.mark.asyncio
async def test_context_is_isolated_between_concurrent_tasks() -> None:
    scopes = [CapabilityScope.create(f"p-{index}", {str(index)}) for index in range(4)]
    ready = asyncio.Event()
    arrived = 0
    lock = asyncio.Lock()

    async def worker(scope: CapabilityScope) -> CapabilityScope | None:
        nonlocal arrived
        token = bind_capability_scope(scope)
        try:
            async with lock:
                arrived += 1
                if arrived == len(scopes):
                    ready.set()
            await ready.wait()
            await asyncio.sleep(0)
            return get_capability_scope()
        finally:
            reset_capability_scope(token)

    assert await asyncio.gather(*(worker(scope) for scope in scopes)) == scopes
    assert get_capability_scope() is None
