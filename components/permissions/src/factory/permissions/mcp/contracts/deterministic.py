"""Strict deterministic Permissions MCP DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue, field_validator

from .base import (
    EmptyInput,
    Identifier,
    OutputModel,
    ToolName,
    _MAX_LIST_ITEMS,
    bounded_json,
)


class ToolCatalog(OutputModel):
    deterministic: list[ToolName] = Field(max_length=32)
    operational: list[ToolName] = Field(max_length=32)
    authoring: list[ToolName] = Field(default_factory=list, max_length=32)


class CapabilitiesOutput(OutputModel):
    schema_version: int = Field(ge=1, le=100)
    tools: ToolCatalog
    cedar_enabled: bool


class HealthOutput(OutputModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    policies_loaded: int = Field(ge=0, le=_MAX_LIST_ITEMS)
    roles_loaded: int = Field(ge=0, le=_MAX_LIST_ITEMS)


class ConfigSchemaOutput(OutputModel):
    settings: dict[str, JsonValue]
    policy: dict[str, JsonValue]

    @field_validator("settings", "policy")
    @classmethod
    def _bounded_schema(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        bounded_json(value, label="schema")
        return value


class RoleSummary(OutputModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4_096)
    permissions: list[str] = Field(default_factory=list, max_length=256)
    inherits: list[Identifier] = Field(default_factory=list, max_length=128)


class RoleRegistryOutput(OutputModel):
    roles: list[RoleSummary] = Field(max_length=_MAX_LIST_ITEMS)
    count: int = Field(ge=0, le=_MAX_LIST_ITEMS)


class PolicySummary(OutputModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=256)
    version: str = Field(max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=256)
    rules_count: int = Field(ge=0, le=_MAX_LIST_ITEMS)


class PolicyRegistryOutput(OutputModel):
    policies: list[PolicySummary] = Field(max_length=_MAX_LIST_ITEMS)
    count: int = Field(ge=0, le=_MAX_LIST_ITEMS)


__all__ = [
    "CapabilitiesOutput",
    "ConfigSchemaOutput",
    "EmptyInput",
    "HealthOutput",
    "PolicyRegistryOutput",
    "PolicySummary",
    "RoleRegistryOutput",
    "RoleSummary",
    "ToolCatalog",
]
