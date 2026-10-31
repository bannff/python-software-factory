"""Pydantic DTOs for the canonical portable Graph core MCP family."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt

from ..runtime.neighbor_limits import DEFAULT_NEIGHBOR_LIMIT, MAX_NEIGHBOR_LIMIT


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityInput(_Input):
    entity_id: str
    entity_type: str
    properties: dict[str, JsonValue] | str | None = None
    labels: list[str] | str | None = None
    backend: str = ""


class UpdateEntityInput(_Input):
    entity_id: str
    properties: dict[str, JsonValue] | str | None = None
    labels: list[str] | str | None = None
    backend: str = ""


class EntityIdInput(_Input):
    entity_id: str
    backend: str = ""


class RelationshipInput(_Input):
    relationship_id: str
    relationship_type: str
    source_id: str
    target_id: str
    properties: dict[str, JsonValue] | None = None
    backend: str = ""


class RelationshipIdInput(_Input):
    relationship_id: str
    backend: str = ""


class NeighborsInput(_Input):
    entity_id: str
    relationship_type: str | None = None
    direction: str = "both"
    limit: StrictInt = Field(default=DEFAULT_NEIGHBOR_LIMIT, ge=1, le=MAX_NEIGHBOR_LIMIT)
    backend: str = ""


class PathInput(_Input):
    source_id: str
    target_id: str
    max_depth: int = 5
    backend: str = ""


class FindEntitiesInput(_Input):
    entity_type: str | None = None
    properties: dict[str, JsonValue] | None = None
    limit: int = 100
    backend: str = ""


class BackendInput(_Input):
    backend: str = ""


class FindingStateInput(_Input):
    finding_id: str
    state: str
    backend: str = ""


class EntityData(BaseModel):
    id: str
    type: str
    properties: dict[str, JsonValue]
    labels: list[str] = []


class RelationshipData(BaseModel):
    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, JsonValue]


class EntityLookupData(BaseModel):
    found: bool
    entity_id: str
    entity: EntityData | None = None
    error: str | None = None
    available: list[str] | None = None


class NeighborsData(BaseModel):
    entity_id: str
    neighbors: list[EntityData]
    count: int
    error: str | None = None
    available: list[str] | None = None


class PathData(BaseModel):
    found: bool
    source_id: str
    target_id: str
    length: int | None = None
    entities: list[EntityData] = []
    relationships: list[RelationshipData] = []
    error: str | None = None
    available: list[str] | None = None


class EntitySearchData(BaseModel):
    entities: list[EntityData]
    count: int
    error: str | None = None
    available: list[str] | None = None


class GraphStatsData(BaseModel):
    backend: str
    node_count: int
    edge_count: int
    healthy: bool
    latency_ms: float
    error: str | None = None
    available: list[str] | None = None


class DeleteOutcomeData(BaseModel):
    success: bool
    identifier: str
    error: str | None = None
    available: list[str] | None = None


class UpdateOutcomeData(BaseModel):
    success: bool
    entity: EntityData | None = None
    error: str | None = None
    available: list[str] | None = None


class FindingStateData(BaseModel):
    success: bool
    finding_id: str
    state: str
    error: str | None = None
    valid: list[str] = []
    available: list[str] | None = None
