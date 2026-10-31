"""Ambient native-envelope replay keys at the typed boundary."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from factory.mcp_utils.context import reset_envelope, set_envelope
from factory.mcp_utils.decorators import operational
from factory.mcp_utils.runtime.idempotency import cache_clear
from factory.mcp_utils.runtime.tool_result import ToolResult


class _Output(BaseModel):
    value: int


@pytest.fixture(autouse=True)
def _clean_cache():
    cache_clear()
    yield
    cache_clear()


@pytest.mark.parametrize("attribute", ["workflow_attempt_id", "idempotency_key"])
def test_ambient_attribute_is_the_typed_replay_key(attribute: str) -> None:
    calls = {"count": 0}

    @operational(output_model=_Output)
    def tool(value: int, idempotency_key: str | None = None) -> _Output:
        calls["count"] += 1
        return _Output(value=value + calls["count"])

    key = f"ambient-{attribute}"
    token = set_envelope({
        "principal_id": "principal", "attributes": {attribute: key},
    })
    try:
        first = tool(3)
        replay = tool(3)
    finally:
        reset_envelope(token)

    assert isinstance(first, ToolResult) and isinstance(replay, ToolResult)
    assert first.data is not None and replay.data is not None
    assert first.data.value == replay.data.value == 4
    assert first.idempotency_key == replay.idempotency_key == key
    assert calls["count"] == 1


def test_explicit_key_wins_over_ambient_replay_key() -> None:
    calls = {"count": 0}

    @operational(output_model=_Output)
    def tool(value: int, idempotency_key: str | None = None) -> _Output:
        calls["count"] += 1
        return _Output(value=value + calls["count"])

    token = set_envelope({
        "principal_id": "principal",
        "attributes": {"workflow_attempt_id": "ambient-key"},
    })
    try:
        first = tool(3, idempotency_key="explicit-key")
        replay = tool(3, idempotency_key="explicit-key")
    finally:
        reset_envelope(token)

    assert first.idempotency_key == replay.idempotency_key == "explicit-key"
    assert calls["count"] == 1


def test_ambient_key_does_not_change_untyped_tool_behavior() -> None:
    calls = {"count": 0}

    @operational
    def tool() -> dict[str, int]:
        calls["count"] += 1
        return {"count": calls["count"]}

    token = set_envelope({
        "principal_id": "principal",
        "attributes": {"workflow_attempt_id": "ambient-key"},
    })
    try:
        assert tool() == {"count": 1}
        assert tool() == {"count": 2}
    finally:
        reset_envelope(token)
    assert calls["count"] == 2
