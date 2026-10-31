"""Strict DTOs for the Oracle MCP boundary."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    """Reject unknown or coerced public boundary values."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    """Input DTO for a tool with no public arguments."""


class CapabilitiesOutput(StrictModel):
    name: str
    version: str
    features: list[str]


class HealthOutput(StrictModel):
    healthy: bool
    verifiers: int


class ConfigSchemaOutput(StrictModel):
    type: Literal["object"]
    additional_properties: bool = Field(serialization_alias="additionalProperties")
    properties: dict[str, JsonValue]


class VerifiersOutput(StrictModel):
    domains: list[str]
    count: int


class StatesOutput(StrictModel):
    states: list[str]


class VerifyFindingInput(StrictModel):
    finding_id: str
    domain: str = ""
    backend: str = ""


class VerifyFindingOutput(StrictModel):
    success: bool
    finding_id: str
    persisted: bool
    state: str | None = None
    evidence: JsonValue | None = None
    verifier: str | None = None
    error: str | None = None


__all__ = [
    "CapabilitiesOutput",
    "ConfigSchemaOutput",
    "EmptyInput",
    "HealthOutput",
    "StatesOutput",
    "StrictModel",
    "VerifyFindingInput",
    "VerifyFindingOutput",
    "VerifiersOutput",
]
