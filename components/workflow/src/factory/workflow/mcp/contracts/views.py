"""DTOs for Workflow dashboard MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class ActivityInput(DTO):
    run_id: str
    limit: int = 20


class GraphContextInput(DTO):
    run_id: str
    limit: int = 12


class RunTasksInput(DTO):
    run_id: str
    limit: int = 20


class DashboardOutput(DTO):
    overview: JsonObject
    series: list[JsonObject]
    task_series: list[JsonObject]
    runs: list[JsonObject]
    tasks: list[JsonObject]
    recent_activity: list[JsonObject]
    related_graph_entities: list[JsonObject]


class EntriesOutput(DTO):
    run_id: str
    entries: list[JsonObject]
    count: int


class ViewsOutput(DTO):
    views: list[JsonObject]
