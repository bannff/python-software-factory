"""DTOs for deterministic Storage MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class CapabilitiesOutput(DTO):
    name: str
    version: str
    storage_types: list[str]
    backends: dict[str, list[str]]
    features: list[str]


class StoreHealth(DTO):
    healthy: bool
    backend: str


class HealthOutput(DTO):
    healthy: bool
    stores: dict[str, StoreHealth]


class ConfigSchemaOutput(DTO):
    type: str
    properties: JsonObject


class ViewsOutput(DTO):
    views: list[JsonObject]
