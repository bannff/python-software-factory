"""Strict deterministic Worker MCP DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from .base import (
    BackendName,
    EmptyInput,
    JsonObject,
    OutputModel,
    QueueName,
    ToolName,
    _MAX_ITEMS,
)


class CapabilitiesOutput(OutputModel):
    name: Literal["worker"]
    version: str = Field(min_length=1, max_length=64)
    backends: list[BackendName] = Field(max_length=3)
    features: list[str] = Field(max_length=32)


class HealthOutput(OutputModel):
    healthy: bool
    backend: BackendName
    active_tasks: int = Field(ge=0, le=1_000_000_000)
    queues: list[QueueName] = Field(max_length=256)
    error: str | None = Field(default=None, max_length=128)


class ConfigSchemaOutput(OutputModel):
    type: Literal["object"]
    properties: JsonObject
    unsupported: list[str] = Field(default_factory=list, max_length=32)


class TaskSummary(OutputModel):
    name: ToolName
    queue: QueueName
    state: str = Field(min_length=1, max_length=64)
    result: JsonValue | None = None


class TaskListOutput(OutputModel):
    tasks: list[TaskSummary] = Field(max_length=_MAX_ITEMS)
    count: int = Field(ge=0, le=_MAX_ITEMS)
    error: str | None = Field(default=None, max_length=128)


__all__ = [
    "CapabilitiesOutput",
    "ConfigSchemaOutput",
    "EmptyInput",
    "HealthOutput",
    "TaskListOutput",
    "TaskSummary",
]
