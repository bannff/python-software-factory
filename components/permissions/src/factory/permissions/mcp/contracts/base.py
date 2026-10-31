"""Shared strict DTO primitives for the Permissions MCP boundary."""
from __future__ import annotations

from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from factory.mcp_utils.interface import is_bounded_json

JsonObject: TypeAlias = dict[str, JsonValue]
JsonArray: TypeAlias = list[JsonValue]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
ToolName = Annotated[str, Field(min_length=1, max_length=256)]

_MAX_BATCH_REQUESTS = 100
_MAX_LIST_ITEMS = 1_024


class StrictModel(BaseModel):
    """Reject unknown fields and all Pydantic input coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


class OutputModel(StrictModel):
    """Strict output DTO with a final finite/bounded JSON guard."""

    @model_validator(mode="after")
    def _bounded_output(self) -> "OutputModel":
        bounded_json(self.model_dump(mode="json"), label="output")
        return self


class EmptyInput(StrictModel):
    """Input for a tool that accepts no public fields."""


def bounded_json(value: object, *, label: str) -> object:
    """Validate finite, size-bounded JSON at the transport boundary."""
    if not is_bounded_json(value):
        raise ValueError(f"{label} must be bounded JSON")
    return value


def bounded_object(value: object, *, label: str) -> JsonObject:
    """Validate a bounded JSON object, not an arbitrary JSON scalar."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    bounded_json(value, label=label)
    return value


__all__ = [
    "EmptyInput",
    "Identifier",
    "JsonArray",
    "JsonObject",
    "OutputModel",
    "StrictModel",
    "ToolName",
    "_MAX_BATCH_REQUESTS",
    "_MAX_LIST_ITEMS",
    "bounded_json",
    "bounded_object",
]
