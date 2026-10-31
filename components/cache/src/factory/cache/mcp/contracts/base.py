"""Shared strict Cache MCP contract DTOs."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base for closed, non-coercing Cache MCP DTOs."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    """Closed input for no-argument tools."""


class CacheHealthOutput(StrictModel):
    healthy: bool
    backend: str = Field(max_length=128)


class ConfigOptionOutput(StrictModel):
    type: str = Field(max_length=32)
    description: str = Field(max_length=256)
    enum: list[str] | None = Field(default=None, max_length=16)


class ConfigSchemaOutput(StrictModel):
    type: str = Field(max_length=32)
    properties: dict[str, ConfigOptionOutput] = Field(max_length=16)
