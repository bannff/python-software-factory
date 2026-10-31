"""Generic typed egress envelope for MCP tools.

Every tool that opts into typed egress returns ``ToolResult[T]`` instead of a
bare ``dict[str, Any]``. FastMCP serializes the model; callers get a stable
contract with ``ok`` / ``data`` / ``error`` / ``idempotency_key``.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):
    """Versioned envelope for MCP tool egress."""

    schema_version: Literal["v1"] = "v1"
    ok: bool = True
    data: T | None = None
    error: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def _check_outcome(self) -> "ToolResult[T]":
        if self.ok and self.error is not None:
            raise ValueError("successful ToolResult cannot contain an error")
        if not self.ok and (self.data is not None or not self.error):
            raise ValueError("failed ToolResult requires an error and no data")
        return self


def with_idempotency_key(result: ToolResult[T], key: str) -> ToolResult[T]:
    """Return a validated copy with a bounded idempotency key."""
    return ToolResult(
        schema_version=result.schema_version,
        ok=result.ok,
        data=result.data,
        error=result.error,
        idempotency_key=key,
    )


def ok(data: T, *, idempotency_key: str | None = None) -> ToolResult[T]:
    """Build a successful tool result."""
    return ToolResult(ok=True, data=data, idempotency_key=idempotency_key)


def fail(error: str, *, idempotency_key: str | None = None) -> ToolResult[None]:
    """Build a failed tool result."""
    return ToolResult(ok=False, data=None, error=error, idempotency_key=idempotency_key)


__all__ = ["ToolResult", "ok", "fail", "with_idempotency_key"]
