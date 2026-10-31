"""Strict operational Worker MCP DTOs."""
from __future__ import annotations

from pydantic import Field, JsonValue

from .base import (
    EmptyInput,
    JsonArray,
    JsonObject,
    OutputModel,
    StrictModel,
    ToolName,
    _MAX_ITEMS,
)


class SendTaskInput(StrictModel):
    name: ToolName
    args: JsonArray | None = None
    kwargs: JsonObject | None = None


class ExecuteToolInput(StrictModel):
    tool_name: ToolName
    arguments: JsonObject | None = None


class SendTaskOutput(OutputModel):
    dispatched: bool
    task: ToolName
    result: JsonValue | None = None
    error: str | None = Field(default=None, max_length=128)


class ExecuteToolOutput(OutputModel):
    tool: ToolName
    result: JsonValue | None = None
    error: str | None = Field(default=None, max_length=128)
    available: list[ToolName] = Field(default_factory=list, max_length=_MAX_ITEMS)


class ListMcpToolsOutput(OutputModel):
    tools: list[ToolName] = Field(max_length=_MAX_ITEMS)
    count: int = Field(ge=0, le=_MAX_ITEMS)
    error: str | None = Field(default=None, max_length=128)


__all__ = [
    "EmptyInput",
    "ExecuteToolInput",
    "ExecuteToolOutput",
    "ListMcpToolsOutput",
    "SendTaskInput",
    "SendTaskOutput",
]
