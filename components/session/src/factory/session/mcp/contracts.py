"""Strict MCP contracts for the session brick."""
from __future__ import annotations

from typing import Any, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def _json_arrays_as_tuples(cls, data: Any) -> Any:
        """Strict mode rejects a JSON array for a ``tuple`` field, and arrays are
        the only sequence the wire has; accept them for the tuple-typed fields."""
        if not isinstance(data, dict):
            return data
        return {
            key: tuple(value) if isinstance(value, list)
            and key in cls.model_fields and get_origin(cls.model_fields[key].annotation) is tuple
            else value
            for key, value in data.items()
        }


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
