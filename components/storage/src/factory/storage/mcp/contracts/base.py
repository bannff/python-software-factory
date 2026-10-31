"""Shared strict JSON-safe DTOs for Storage FastMCP boundaries."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject = dict[str, JsonValue]
JsonArray = list[JsonValue]


class DTO(BaseModel):
    """Strict same-brick transport contract base."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat empty input for contract tools."""


class NodeData(DTO):
    id: str
    labels: list[str]
    properties: JsonObject


class EdgeData(DTO):
    id: str
    source_id: str
    target_id: str
    type: str
    properties: JsonObject
