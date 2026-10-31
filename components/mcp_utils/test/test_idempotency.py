"""Process-local idempotency cache + decorator replay."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, Field

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.runtime.idempotency import (
    cache_clear,
    cache_get,
    cache_put,
    cache_size,
)
from factory.mcp_utils.runtime.schema_migration import clear_steps
from factory.mcp_utils.runtime.tool_result import ToolResult, fail, ok
from factory.mcp_utils.context import reset_envelope, set_envelope


class _Out(BaseModel):
    schema_version: Literal["v1"] = "v1"
    value: int = Field(..., ge=0)


class _In(BaseModel):
    schema_version: Literal["v1"] = "v1"
    value: int = 0
    idempotency_key: str | None = None


@pytest.fixture(autouse=True)
def _clean():
    token = set_envelope({"principal_id": "test-principal"})
    cache_clear()
    clear_steps()
    yield
    cache_clear()
    clear_steps()
    reset_envelope(token)


def test_cache_roundtrip() -> None:
    result = ok(_Out(value=3), idempotency_key="k")
    cache_put("scope", "k", result)
    hit = cache_get("scope", "k")
    assert hit is not None
    assert hit.data is not None
    assert hit.data["value"] == 3 or hit.data.value == 3  # type: ignore[union-attr]


def test_cache_skips_failures() -> None:
    cache_put("scope", "k", fail("nope", idempotency_key="k"))
    assert cache_get("scope", "k") is None
    assert cache_size() == 0


def test_cache_rejects_overlong_key_instead_of_bypassing_validation() -> None:
    result = ok(_Out(value=3))
    with pytest.raises(Exception):
        cache_put("scope", "k" * 257, result)
    assert cache_size() == 0


def test_decorator_replays_on_same_key() -> None:
    calls = {"n": 0}
    valid_key = "k" * 256

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=value + calls["n"])

    a = tool(value=10, idempotency_key=valid_key)
    b = tool(value=10, idempotency_key=valid_key)
    assert isinstance(a, ToolResult) and isinstance(b, ToolResult)
    assert a.ok and b.ok
    assert a.data is not None and b.data is not None
    assert a.data.value == b.data.value == 11
    assert calls["n"] == 1
    assert a.idempotency_key == b.idempotency_key == valid_key


def test_same_key_with_changed_input_returns_conflict_without_provider() -> None:
    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=value)

    first = tool(value=1, idempotency_key="same")
    second = tool(value=2, idempotency_key="same")
    assert first.ok
    assert second == ToolResult(ok=False, data=None, error="idempotency_key_conflict")
    assert calls["n"] == 1


def test_different_context_does_not_replay() -> None:
    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=calls["n"])

    first = tool(value=1, idempotency_key="context-key")
    token = set_envelope({"principal_id": "other-principal"})
    try:
        second = tool(value=1, idempotency_key="context-key")
    finally:
        reset_envelope(token)
    assert first.data is not None and second.data is not None
    assert first.data.value == 1
    assert second.data.value == 2
    assert calls["n"] == 2


def test_concurrent_same_key_executes_provider_once() -> None:
    from concurrent.futures import ThreadPoolExecutor
    import time

    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        time.sleep(0.05)
        return _Out(value=calls["n"])

    def invoke() -> ToolResult[_Out]:
        token = set_envelope({"principal_id": "thread-principal"})
        try:
            return tool(value=1, idempotency_key="concurrent")
        finally:
            reset_envelope(token)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: invoke(), range(8)))
    assert calls["n"] == 1
    assert {result.data.value for result in results if result.data is not None} == {1}


def test_sync_overlong_key_fails_before_provider_and_cache() -> None:
    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=value)

    result = tool(value=3, idempotency_key="k" * 257)
    assert result == ToolResult(ok=False, data=None, error="tool_execution_failed")
    assert calls["n"] == 0
    assert cache_size() == 0


@pytest.mark.asyncio
async def test_async_overlong_key_fails_before_provider_and_cache() -> None:
    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    async def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=value)

    result = await tool(value=3, idempotency_key="k" * 257)
    assert result == ToolResult(ok=False, data=None, error="tool_execution_failed")
    assert calls["n"] == 0
    assert cache_size() == 0


def test_decorator_different_keys_not_shared() -> None:
    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=calls["n"])

    tool(value=1, idempotency_key="a")
    tool(value=1, idempotency_key="b")
    assert calls["n"] == 2


def test_no_key_always_executes() -> None:
    calls = {"n": 0}

    @operational(input_model=_In, output_model=_Out)
    def tool(*, value: int = 0, idempotency_key: str | None = None) -> _Out:
        calls["n"] += 1
        return _Out(value=calls["n"])

    tool(value=1)
    tool(value=1)
    assert calls["n"] == 2
