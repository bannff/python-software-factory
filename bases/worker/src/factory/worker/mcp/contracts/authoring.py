"""Strict authoring Worker MCP DTOs."""
from __future__ import annotations

from pydantic import Field

from .base import (
    BackendName,
    EmptyInput,
    JsonObject,
    OutputModel,
    QueueName,
    StrictModel,
)


class SwitchBackendInput(StrictModel):
    backend: str = Field(min_length=1, max_length=64)
    broker_url: str | None = Field(default=None, max_length=2_048)


class SetConfigInput(StrictModel):
    queues: list[QueueName] | None = Field(default=None, max_length=256)
    concurrency: int | None = Field(default=None, ge=1, le=10_000)


class AuthoringStatusOutput(OutputModel):
    enabled: bool
    available_backends: list[BackendName] = Field(max_length=3)
    current_backend: BackendName


class SwitchBackendOutput(OutputModel):
    switched: bool
    backend: BackendName | None = None
    requested: str | None = Field(default=None, max_length=64)
    available: list[BackendName] = Field(max_length=3)
    error: str | None = Field(default=None, max_length=128)


class SetConfigOutput(OutputModel):
    updated: bool
    changes: JsonObject = Field(default_factory=dict)
    unsupported: list[str] = Field(default_factory=list, max_length=16)
    error: str | None = Field(default=None, max_length=128)


__all__ = [
    "AuthoringStatusOutput",
    "EmptyInput",
    "SetConfigInput",
    "SetConfigOutput",
    "SwitchBackendInput",
    "SwitchBackendOutput",
]
