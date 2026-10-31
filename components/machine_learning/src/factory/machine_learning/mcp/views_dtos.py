"""Strict Pydantic DTOs for the ML declared-view read tool."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(_DTO):
    pass


class ViewsOutput(_DTO):
    views: list[dict[str, Any]]
