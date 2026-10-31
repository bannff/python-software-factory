"""Strict DTOs for the human-action dispatch MCP boundary."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DispatchActionInput(_Input):
    action: dict[str, Any]
    args: dict[str, Any] | None = None
    thread_id: str | None = None
    principal_id: str | None = None


class DispatchActionOutput(_Output):
    """The established nested action outcome, kept inside a successful envelope."""

    ok: bool
    error: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: Any | None = None
    invalidates: list[str] | None = None


__all__ = ["DispatchActionInput", "DispatchActionOutput"]
