"""Strict DTOs for brick-view ingestion and rendering MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RegisterBrickViewsInput(_Input):
    views: list[dict[str, Any]]


class RegistrationError(_Output):
    id: str
    error: str


class RegisterBrickViewsOutput(_Output):
    registered: list[str]
    count: int
    errors: list[RegistrationError]


class RenderViewInput(_Input):
    view_id: str
    adapter: str = "htmx"


class RenderViewOutput(_Output):
    view_id: str
    adapter: str
    content_type: str
    content: Any
    metadata: dict[str, Any]


__all__ = [
    "RegisterBrickViewsInput", "RegisterBrickViewsOutput", "RenderViewInput",
    "RenderViewOutput",
]
