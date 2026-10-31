"""Pydantic contracts for Graph contract and dashboard helpers."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue


class NoArgsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str
    limit: int = 12


class CapabilitiesData(BaseModel):
    name: str
    version: str
    active_backend: str
    backends: list[str]
    features: list[str]
    tools: dict[str, list[str]] = {}
    mcp_resources: list[str]
    mcp_prompts: list[str]


class HealthGraphData(BaseModel):
    healthy: bool
    nodes: int
    edges: int


class HealthData(BaseModel):
    healthy: bool
    graphs: dict[str, HealthGraphData]
    message: str | None = None


class ConfigSchemaData(BaseModel):
    type: str
    properties: dict[str, dict[str, JsonValue]]
    required: list[str]


class RecentRunsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = 20
    backend: str = ""


class RecentRunData(BaseModel):
    id: str
    run_id: str
    status: str
    started_at: str


class RecentRunsData(BaseModel):
    runs: list[RecentRunData]
    count: int
    error: str | None = None
    available: list[str] | None = None


class DashboardSummaryData(BaseModel):
    overview: dict[str, JsonValue]
    series: list[dict[str, JsonValue]]
    entities: list[dict[str, JsonValue]]
    neighborhoods: list[dict[str, JsonValue]]


class EntityContextData(BaseModel):
    entity_id: str
    entries: list[dict[str, JsonValue]]
    count: int


class ViewsData(BaseModel):
    views: list[dict[str, JsonValue]]
