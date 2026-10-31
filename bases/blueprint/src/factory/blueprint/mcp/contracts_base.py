"""Shared strict, JSON-safe DTO primitives for Blueprint MCP tools."""
from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject: TypeAlias = dict[str, JsonValue]


class StrictInput(BaseModel):
    """Reject unknown or coerced fields at the Blueprint MCP boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictInput):
    """Strict input DTO for no-argument tools."""


class JsonOutput(BaseModel):
    """Ensure output DTOs expose only recursively JSON-safe data."""

    model_config = ConfigDict(extra="forbid")
