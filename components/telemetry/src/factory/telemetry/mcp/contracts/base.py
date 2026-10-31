"""Shared strict JSON-safe DTOs for Telemetry native MCP v2 boundaries."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject = dict[str, JsonValue]


class DTO(BaseModel):
    """Strict same-brick transport contract base."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat empty input for no-argument tools."""
