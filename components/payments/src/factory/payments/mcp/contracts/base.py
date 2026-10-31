"""Strict, secret-safe primitives for the Payments MCP boundary."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, model_validator

_SENSITIVE = re.compile(
    r"(?:api[_-]?key|public[_-]?key|secret|token|authorization|webhook[_-]?secret|"
    r"client[_-]?secret|card|pan|cvv|cvc|payment[_-]?method)", re.I,
)
_PAN = re.compile(r"(?:\d[ -]?){13,19}$")
_MAX_DEPTH = 8
_MAX_NODES = 100


class StrictModel(BaseModel):
    """Reject unknown fields and coercion at the public MCP boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    """Strict DTO for a tool with no public inputs."""


def safe_json(value: Any, *, path: str = "", depth: int = 0, nodes: list[int] | None = None) -> Any:
    """Validate bounded JSON while rejecting credential and card material."""
    nodes = nodes if nodes is not None else [0]
    nodes[0] += 1
    if depth > _MAX_DEPTH or nodes[0] > _MAX_NODES:
        raise ValueError("payload_too_complex")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or _SENSITIVE.search(key):
                raise ValueError("sensitive_payload_field")
            safe_json(child, path=key, depth=depth + 1, nodes=nodes)
    elif isinstance(value, list):
        for child in value:
            safe_json(child, path=path, depth=depth + 1, nodes=nodes)
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError("payload_must_be_json_safe")
    elif isinstance(value, str) and _PAN.fullmatch(value.replace(" ", "").replace("-", "")):
        raise ValueError("sensitive_payment_value")
    return value


class SafeJsonInput(StrictModel):
    """Base model that recursively checks metadata/options fields."""

    @model_validator(mode="after")
    def _validate_json_fields(self) -> "SafeJsonInput":
        for name in ("metadata", "options", "payload"):
            value = getattr(self, name, None)
            if value is not None:
                safe_json(value)
        return self


__all__ = ["EmptyInput", "SafeJsonInput", "SecretStr", "StrictModel"]
