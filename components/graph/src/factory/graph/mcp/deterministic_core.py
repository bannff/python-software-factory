"""Canonical typed portable Graph core read tools."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .core_models import (
    BackendInput, EntityData, EntityIdInput, EntityLookupData, EntitySearchData,
    FindEntitiesInput, GraphStatsData, NeighborsData, NeighborsInput, PathData,
    PathInput, RelationshipData,
)
from ..runtime.neighbor_limits import DEFAULT_NEIGHBOR_LIMIT

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def _entity(entity) -> EntityData:
    return EntityData(id=entity.id, type=entity.type, properties=entity.properties,
                      labels=entity.labels)


def _relationship(relationship) -> RelationshipData:
    return RelationshipData(id=relationship.id, type=relationship.type,
                            source_id=relationship.source_id,
                            target_id=relationship.target_id,
                            properties=relationship.properties)


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register portable typed core reads under their canonical names."""

    @typed_tool(mcp)
    @deterministic(input_model=EntityIdInput, output_model=EntityLookupData)
    def graph_get_entity(entity_id: str, backend: str = "") -> ToolResult[EntityLookupData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return EntityLookupData(found=False, entity_id=entity_id,
                                    error="unknown_backend", available=available)
        entity = runtime.get_graph(selected).get_entity(entity_id)
        return EntityLookupData(found=entity is not None, entity_id=entity_id,
                                entity=_entity(entity) if entity else None)

    @typed_tool(mcp)
    @deterministic(input_model=NeighborsInput, output_model=NeighborsData)
    def graph_get_neighbors(entity_id: str, relationship_type: str | None = None,
                            direction: str = "both", backend: str = "",
                            limit: int = DEFAULT_NEIGHBOR_LIMIT) -> ToolResult[NeighborsData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return NeighborsData(entity_id=entity_id, neighbors=[], count=0,
                                 error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        neighbors = graph.get_neighbors(
            entity_id, relationship_type, direction, limit=limit,
        )
        return NeighborsData(entity_id=entity_id, neighbors=[_entity(item) for item in neighbors],
                             count=len(neighbors))

    @typed_tool(mcp)
    @deterministic(input_model=PathInput, output_model=PathData)
    def graph_find_path(source_id: str, target_id: str, max_depth: int = 5,
                        backend: str = "") -> ToolResult[PathData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return PathData(found=False, source_id=source_id, target_id=target_id,
                            error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        path = graph.find_path(source_id, target_id, max_depth)
        if path is None:
            return PathData(found=False, source_id=source_id, target_id=target_id)
        return PathData(found=True, source_id=source_id, target_id=target_id,
                        length=path.length, entities=[_entity(item) for item in path.entities],
                        relationships=[_relationship(item) for item in path.relationships])

    @typed_tool(mcp)
    @deterministic(input_model=FindEntitiesInput, output_model=EntitySearchData)
    def graph_find_entities(entity_type: str | None = None, properties: dict | None = None,
                            limit: int = 100, backend: str = "") -> ToolResult[EntitySearchData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return EntitySearchData(entities=[], count=0,
                                    error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        entities = graph.find_entities(entity_type, properties, limit)
        return EntitySearchData(entities=[_entity(item) for item in entities], count=len(entities))

    @typed_tool(mcp)
    @deterministic(input_model=BackendInput, output_model=GraphStatsData)
    def graph_get_stats(backend: str = "") -> ToolResult[GraphStatsData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return GraphStatsData(backend=selected, node_count=0, edge_count=0,
                                  healthy=False, latency_ms=0.0,
                                  error="unknown_backend", available=available)
        health = runtime.get_graph(selected).health_check()
        return GraphStatsData(backend=selected, node_count=health.node_count,
                              edge_count=health.edge_count, healthy=health.healthy,
                              latency_ms=health.latency_ms)
