"""Tests for ToolResult egress envelope + decorator I/O model wiring."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, Field

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.runtime.schema_migration import (
    clear_steps,
    register_step,
)
from factory.mcp_utils.runtime.tool_result import ToolResult, fail, ok


class _Payload(BaseModel):
    schema_version: Literal["v1"] = "v1"
    doc_id: str = Field(..., min_length=1)
    chunk_count: int = 0


class _Req(BaseModel):
    schema_version: Literal["v1", "v2"] = "v2"
    content: str = Field(..., min_length=1)
    doc_id: str | None = None


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_steps()
    yield
    clear_steps()


def test_ok_helper() -> None:
    result = ok(_Payload(doc_id="a", chunk_count=2), idempotency_key="k1")
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.data is not None
    assert result.data.doc_id == "a"
    assert result.idempotency_key == "k1"


def test_fail_helper() -> None:
    result = fail("boom", idempotency_key="k2")
    assert result.ok is False
    assert result.data is None
    assert result.error == "boom"


def test_tool_result_allows_successful_null_domain_state() -> None:
    assert ToolResult(ok=True, data=None, error=None).ok is True
    with pytest.raises(Exception):
        ToolResult(ok=False, data="unexpected", error="failed")


def test_operational_output_model_wraps_dict() -> None:
    @operational(output_model=_Payload)
    def tool() -> dict:
        return {"doc_id": "x", "chunk_count": 3}

    result = tool()
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data.doc_id == "x"


def test_operational_passthrough_without_models() -> None:
    @operational
    def tool() -> dict[str, str]:
        return {"status": "ok"}

    assert tool() == {"status": "ok"}
    assert getattr(tool, "_mcp_category") == "operational"


def test_operational_preserves_existing_tool_result() -> None:
    @operational(output_model=_Payload)
    def tool() -> ToolResult[_Payload]:
        return ok(_Payload(doc_id="z"), idempotency_key="keep")

    assert tool().idempotency_key == "keep"


def test_operational_validates_existing_tool_result_data() -> None:
    @operational(output_model=_Payload)
    def tool() -> ToolResult[dict[str, str]]:
        return ok({"doc_id": "", "chunk_count": "not-an-int"})

    result = tool()
    assert result == ToolResult(ok=False, data=None, error="tool_execution_failed")


def test_operational_normalizes_egress_idempotency_validation_failure() -> None:
    @operational(output_model=_Payload)
    def tool(*, idempotency_key: str | None = None) -> dict:
        return {"doc_id": "x", "chunk_count": 1}

    result = tool(idempotency_key="k" * 257)
    assert result == ToolResult(ok=False, data=None, error="tool_execution_failed")


def test_operational_normalizes_sync_invocation_failure(caplog: pytest.LogCaptureFixture) -> None:
    @operational(output_model=_Payload)
    def tool() -> _Payload:
        raise RuntimeError("provider secret: internal endpoint")

    with caplog.at_level("ERROR"):
        result = tool()

    assert result == ToolResult(ok=False, data=None, error="tool_execution_failed")
    assert "provider secret: internal endpoint" not in caplog.text
    assert "typed_mcp_tool_execution_failed tool=" in caplog.text


def test_input_model_flat_kwargs() -> None:
    seen: dict = {}

    @operational(input_model=_Req, output_model=_Payload)
    def tool(*, content: str, doc_id: str | None = None) -> dict:
        seen["content"] = content
        seen["doc_id"] = doc_id
        return {"doc_id": doc_id or "x", "chunk_count": 1}

    result = tool(content="hello", doc_id="d1")
    assert seen == {"content": "hello", "doc_id": "d1"}
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data.doc_id == "d1"


def test_input_model_legacy_dict_migrates() -> None:
    register_step(
        "_Req",
        "v1",
        lambda data: {
            "schema_version": "v2",
            "content": data["body"],
            "doc_id": data.get("doc_id"),
        },
    )
    seen: dict = {}

    @operational(input_model=_Req)
    def tool(*, content: str, doc_id: str | None = None) -> str:
        seen["content"] = content
        seen["doc_id"] = doc_id
        return "ok"

    assert tool({"body": "legacy", "doc_id": "d9"}) == "ok"
    assert seen == {"content": "legacy", "doc_id": "d9"}


def test_input_model_rejects_mixed_args() -> None:
    @operational(input_model=_Req)
    def tool(*, content: str, doc_id: str | None = None) -> str:
        return content

    with pytest.raises(TypeError, match="flat kwargs or a single"):
        tool({"body": "x"}, content="y")


@pytest.mark.asyncio
async def test_operational_async_tool_preserves_awaitable_contract() -> None:
    @operational(output_model=_Payload)
    async def tool() -> dict[str, object]:
        return {"doc_id": "async", "chunk_count": 1}

    result = await tool()
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data.doc_id == "async"


@pytest.mark.asyncio
async def test_operational_normalizes_async_invocation_failure() -> None:
    @operational(output_model=_Payload)
    async def tool() -> _Payload:
        raise RuntimeError("provider secret: async endpoint")

    result = await tool()

    assert result == ToolResult(ok=False, data=None, error="tool_execution_failed")
