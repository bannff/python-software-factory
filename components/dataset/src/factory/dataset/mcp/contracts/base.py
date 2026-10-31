"""Shared strict DTOs for Dataset's public MCP boundary."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class InputDTO(BaseModel):
    """Strict flat ingress contract for Dataset MCP tools."""

    model_config = ConfigDict(extra="forbid", strict=True)


class OutputDTO(BaseModel):
    """Strict public Dataset payload base for stable MCP serialization."""

    model_config = ConfigDict(strict=True, extra="forbid")

    @property
    def root(self) -> dict[str, Any]:
        """Legacy in-process view; MCP serialization remains the concrete DTO."""
        return self.model_dump(mode="json", exclude_none=True)


def validate_strict_json(value: Any) -> Any:
    """Reject coercive nested values while retaining Dataset's dynamic config keys."""
    if value is None or type(value) in {str, int, float, bool}:
        return value
    if isinstance(value, list):
        return [validate_strict_json(item) for item in value]
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: validate_strict_json(item) for key, item in value.items()}
    raise ValueError("nested Dataset config must be JSON scalars, lists, or objects")
