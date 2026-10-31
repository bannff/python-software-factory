"""Shared strict transport DTOs for Browser MCP tools."""
from __future__ import annotations

from math import isfinite
from pydantic import BaseModel, ConfigDict, JsonValue, RootModel, field_validator


def _validate_json(value: JsonValue) -> JsonValue:
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            _validate_json(item)
    return value


class DTO(BaseModel):
    """Strict base for Browser MCP transport models."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Strict request for a tool with no public arguments."""


class JsonObject(RootModel[dict[str, JsonValue]]):
    """A recursively JSON-safe object value."""

    model_config = ConfigDict(strict=True)

    @field_validator("root")
    @classmethod
    def _json_safe(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return _validate_json(value)


class SessionOutput(DTO):
    """Public browser-session representation."""

    session_id: str
    browser_type: str
    headless: bool
    current_url: str | None = None
    created_at: str
    page_count: int = 1
