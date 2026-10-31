"""Shared strict Pydantic v2 DTO bases for Sandbox MCP tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject coercion and unknown fields at the public MCP boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictModel):
    """Strict input DTO for tools that accept no public arguments."""


__all__ = ["EmptyInput", "StrictModel"]
