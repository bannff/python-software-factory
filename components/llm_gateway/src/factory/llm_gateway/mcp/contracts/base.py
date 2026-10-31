"""Strict DTO primitives for the LLM Gateway MCP boundary."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

_MAX_OUTPUT_BYTES = 4 * 1024 * 1024


class StrictModel(BaseModel):
    """Reject unknown fields and Pydantic coercion at the MCP boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class OutputModel(StrictModel):
    """Ensure typed tool output remains finite, JSON-safe, and bounded."""

    @model_validator(mode="after")
    def _bounded_json_output(self) -> "OutputModel":
        try:
            encoded = json.dumps(
                self.model_dump(mode="json"),
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("output must be finite JSON") from exc
        if len(encoded) > _MAX_OUTPUT_BYTES:
            raise ValueError("output exceeds 4 MiB")
        return self


class EmptyInput(StrictModel):
    """Input DTO for a tool with no public arguments."""


class UsageOutput(OutputModel):
    """Bounded provider token-usage projection."""

    values: dict[str, int]

    @model_validator(mode="after")
    def _bounded_usage(self) -> "UsageOutput":
        if len(self.values) > 32:
            raise ValueError("usage supports at most 32 values")
        if any(
            not key or len(key) > 64 or value < 0 or value > 1_000_000_000
            for key, value in self.values.items()
        ):
            raise ValueError("usage values must be bounded non-negative integers")
        return self


def usage_output(value: dict[str, Any]) -> UsageOutput:
    """Project runtime usage to the strict public usage DTO."""
    return UsageOutput(values=value)


__all__ = [
    "EmptyInput",
    "OutputModel",
    "StrictModel",
    "UsageOutput",
    "usage_output",
]
