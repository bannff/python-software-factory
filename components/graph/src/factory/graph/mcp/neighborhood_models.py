"""Strict MCP DTOs for authority-scoped graph neighborhoods."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from .core_models import EntityData, RelationshipData


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EnvelopeInput(_StrictInput):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    workflow_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    timestamp: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SeedReference(_StrictInput):
    kind: str = Field(min_length=1, max_length=32)
    local_id: str = Field(min_length=1, max_length=128)


class NeighborhoodInput(_StrictInput):
    seed_ids: list[str] = Field(default_factory=list, max_length=20)
    seed_refs: list[SeedReference] = Field(default_factory=list, max_length=20)
    relationship_types: list[str] = Field(default_factory=list, max_length=20)
    direction: Literal["in", "out", "both"] = "both"
    max_depth: StrictInt = Field(default=1, ge=1, le=3)
    node_limit: StrictInt = Field(default=100, ge=1, le=200)
    edge_limit: StrictInt = Field(default=200, ge=1, le=400)
    backend: str = ""
    envelope: EnvelopeInput | None = None

    @model_validator(mode="after")
    def seeds_fit_node_limit(self) -> "NeighborhoodInput":
        count = len(self.seed_ids) + len(self.seed_refs)
        if not 1 <= count <= 20 or (self.seed_ids and self.seed_refs):
            raise ValueError("provide 1..20 seed_ids or seed_refs")
        if count > self.node_limit:
            raise ValueError("node_limit must include every seed")
        return self


class NeighborhoodData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_ids: list[str]
    entities: list[EntityData]
    relationships: list[RelationshipData]
    entity_count: int
    relationship_count: int
    depth_reached: int
    nodes_truncated: bool
    edges_truncated: bool
    backend: str
    error: str | None = None
    available: list[str] | None = None


__all__ = [
    "EnvelopeInput", "NeighborhoodData", "NeighborhoodInput", "SeedReference",
]
