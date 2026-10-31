"""Strict DTO primitives for the Worker MCP boundary."""
from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from factory.mcp_utils.interface import is_bounded_json

JsonObject: TypeAlias = dict[str, JsonValue]
JsonArray: TypeAlias = list[JsonValue]
BackendName = Literal["celery", "dagster", "fargate_sqs"]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]
ToolName = Annotated[str, Field(min_length=1, max_length=256)]
QueueName = Annotated[str, Field(min_length=1, max_length=128)]
_MAX_ITEMS = 1_024


class StrictModel(BaseModel):
    """Reject unknown fields, coercion, and unbounded JSON payloads."""

    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def _bounded_payload(self) -> "StrictModel":
        if not is_bounded_json(self.model_dump(mode="json")):
            raise ValueError("payload must be bounded JSON")
        return self


class OutputModel(StrictModel):
    """Strict output DTO with the shared finite/bounded JSON guard."""

    @model_validator(mode="after")
    def _bounded_output(self) -> "OutputModel":
        if not is_bounded_json(self.model_dump(mode="json")):
            raise ValueError("output must be bounded JSON")
        return self


class EmptyInput(StrictModel):
    """Input DTO for tools that accept no public fields."""


__all__ = [
    "BackendName",
    "EmptyInput",
    "Identifier",
    "JsonArray",
    "JsonObject",
    "OutputModel",
    "QueueName",
    "StrictModel",
    "ToolName",
    "_MAX_ITEMS",
]
