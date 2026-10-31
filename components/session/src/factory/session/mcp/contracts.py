"""Strict MCP contracts for the session brick."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OutputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyInput(InputDTO):
    pass


class CapabilitiesOutput(OutputDTO):
    name: str
    version: str
    features: list[str]


class HealthOutput(OutputDTO):
    healthy: bool
    backend: str


class ConfigSchemaOutput(OutputDTO):
    type: str
    additionalProperties: bool
    properties: dict[str, object] = Field(default_factory=dict)


__all__ = [
    "CapabilitiesOutput", "ConfigSchemaOutput", "EmptyInput", "HealthOutput",
]
