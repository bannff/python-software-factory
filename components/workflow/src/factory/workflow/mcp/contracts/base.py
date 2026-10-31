"""Strict JSON-safe transport DTOs for Workflow MCP tools."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, JsonValue

JsonObject = dict[str, JsonValue]


class DTO(BaseModel):
    """Same-brick strict public transport contract base."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Flat input for no-argument tools."""


def json_safe(value: Any) -> JsonValue:
    """Convert runtime values, including datetimes, to JSON-safe data."""

    return json.loads(json.dumps(value, default=str))
