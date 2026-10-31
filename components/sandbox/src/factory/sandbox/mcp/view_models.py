"""Typed DTOs for Sandbox dashboard and view tools."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from .contracts import StrictModel


class DashboardSummaryResult(StrictModel):
    overview: dict[str, Any]
    series: list[dict[str, Any]] = Field(default_factory=list)
    environments: list[dict[str, Any]] = Field(default_factory=list)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)
    related_graph_entities: list[dict[str, Any]] = Field(default_factory=list)
    profiles: list[dict[str, Any]] = Field(default_factory=list)


class EnvironmentActivityRequest(StrictModel):
    env_id: str = Field(min_length=1, max_length=256)
    limit: int = Field(default=20, ge=1, le=100)


class EnvironmentActivityResult(StrictModel):
    env_id: str
    entries: list[dict[str, Any]] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class ViewsResult(StrictModel):
    views: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "DashboardSummaryResult", "EnvironmentActivityRequest",
    "EnvironmentActivityResult", "ViewsResult",
]
