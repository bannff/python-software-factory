"""Shared strict JSON-safe DTOs for Games native MCP v2 boundaries."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue, RootModel

JsonObject = dict[str, JsonValue]


class DTO(BaseModel):
    """Strict same-brick transport contract base."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat empty input for contract tools."""


class JsonOutput(RootModel[JsonObject]):
    """A strict JSON object whose public keys are runtime-defined."""

    model_config = ConfigDict(strict=True)
