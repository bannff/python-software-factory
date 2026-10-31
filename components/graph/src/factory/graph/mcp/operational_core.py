"""Canonical typed portable Graph core mutation tools."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.ports import Entity, Relationship
from .core_models import (
    DeleteOutcomeData, EntityData, EntityIdInput, EntityInput, FindingStateData,
    FindingStateInput, RelationshipData, RelationshipIdInput, RelationshipInput,
    UpdateEntityInput, UpdateOutcomeData,
)

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def _coerce(properties: Any, labels: Any) -> tuple[dict[str, Any] | None, list[str] | None]:
    import json
    if isinstance(properties, str):
        try:
            properties = json.loads(properties)
        except (TypeError, ValueError):
            properties = {}
    if isinstance(labels, str):
        try:
            labels = json.loads(labels)
        except (TypeError, ValueError):
            labels = [item.strip() for item in labels.split(",") if item.strip()]
    return properties, labels


def _entity(entity: Entity) -> EntityData:
    return EntityData(id=entity.id, type=entity.type, properties=entity.properties,
                      labels=entity.labels)


def _relationship(relationship: Relationship) -> RelationshipData:
    return RelationshipData(id=relationship.id, type=relationship.type,
                            source_id=relationship.source_id,
                            target_id=relationship.target_id,
                            properties=relationship.properties)


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register portable typed mutations under their canonical names."""

    @typed_tool(mcp)
    @operational(input_model=EntityInput, output_model=EntityData)
    def graph_add_entity(entity_id: str, entity_type: str, properties: dict | str | None = None,
                         labels: list[str] | str | None = None, backend: str = "") -> ToolResult[EntityData]:
        properties, labels = _coerce(properties, labels)
        graph = get_runtime().get_graph(backend or get_runtime().default_backend)
        return _entity(graph.add_entity(Entity(entity_id, entity_type, properties or {}, labels or [])))

    @typed_tool(mcp)
    @operational(input_model=UpdateEntityInput, output_model=UpdateOutcomeData)
    def graph_update_entity(entity_id: str, properties: dict | str | None = None,
                            labels: list[str] | str | None = None, backend: str = "") -> ToolResult[UpdateOutcomeData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return UpdateOutcomeData(success=False, error="unknown_backend", available=available)
        properties, labels = _coerce(properties, labels)
        graph = runtime.get_graph(selected)
        existing = graph.get_entity(entity_id)
        if existing is None:
            return UpdateOutcomeData(success=False, error=f"Entity not found: {entity_id}")
        updated = graph.update_entity(Entity(entity_id, existing.type,
                                             existing.properties if properties is None else properties,
                                             existing.labels if labels is None else labels))
        return UpdateOutcomeData(success=True, entity=_entity(updated))

    @typed_tool(mcp)
    @operational(input_model=EntityIdInput, output_model=DeleteOutcomeData)
    def graph_delete_entity(entity_id: str, backend: str = "") -> ToolResult[DeleteOutcomeData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return DeleteOutcomeData(success=False, identifier=entity_id,
                                     error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        return DeleteOutcomeData(success=graph.delete_entity(entity_id), identifier=entity_id)

    @typed_tool(mcp)
    @operational(input_model=RelationshipInput, output_model=RelationshipData)
    def graph_add_relationship(relationship_id: str, relationship_type: str, source_id: str,
                               target_id: str, properties: dict | None = None,
                               backend: str = "") -> ToolResult[RelationshipData]:
        graph = get_runtime().get_graph(backend or get_runtime().default_backend)
        return _relationship(graph.add_relationship(Relationship(relationship_id, relationship_type,
                                                                  source_id, target_id, properties or {})))

    @typed_tool(mcp)
    @operational(input_model=RelationshipIdInput, output_model=DeleteOutcomeData)
    def graph_delete_relationship(relationship_id: str, backend: str = "") -> ToolResult[DeleteOutcomeData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return DeleteOutcomeData(success=False, identifier=relationship_id,
                                     error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        return DeleteOutcomeData(success=graph.delete_relationship(relationship_id), identifier=relationship_id)

    @typed_tool(mcp)
    @operational(input_model=FindingStateInput, output_model=FindingStateData)
    def graph_set_finding_state(finding_id: str, state: str, backend: str = "") -> ToolResult[FindingStateData]:
        from ..core import FINDING_STATES
        if state not in FINDING_STATES:
            return FindingStateData(success=False, finding_id=finding_id, state=state,
                                    error=f"invalid state: {state!r}", valid=sorted(FINDING_STATES))
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return FindingStateData(success=False, finding_id=finding_id, state=state,
                                    error="unknown_backend", available=available)
        graph = runtime.get_graph(selected)
        return FindingStateData(success=graph.set_finding_state(finding_id, state),
                                finding_id=finding_id, state=state)
