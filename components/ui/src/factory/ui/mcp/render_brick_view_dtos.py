"""Strict DTOs for inline brick-view rendering."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RenderBrickViewInput(_Input):
    brick_name: str
    view_id: str | None = None


class RenderBrickViewOutput(_Output):
    """The flat A2UI carrier consumed by the inline chat renderer."""

    components: list[dict[str, Any]]
    name: str


__all__ = ["RenderBrickViewInput", "RenderBrickViewOutput"]
