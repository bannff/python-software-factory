"""Deterministic authority-scoped Graph neighborhood MCP tool."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, deterministic, get_envelope, op_kind,
)
from factory.mcp_utils.registration import typed_tool

from .core_models import EntityData, RelationshipData
from .neighborhood_models import NeighborhoodData, NeighborhoodInput
from ..runtime.neighborhood import NeighborhoodRequest, encode_node_id

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=NeighborhoodInput, output_model=NeighborhoodData)
    @op_kind("read")
    def graph_neighborhood(
        seed_ids: list[str] | None = None,
        seed_refs: list[dict[str, str]] | None = None,
        relationship_types: list[str] | None = None,
        direction: str = "both", max_depth: int = 1,
        node_limit: int = 100, edge_limit: int = 200,
        backend: str = "", envelope: dict | None = None,
    ) -> ToolResult[NeighborhoodData]:
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            return _empty(seed_ids or [], selected, "unknown_backend", available)
        authority = _authority(envelope)
        tenant_id, principal_id = authority.get("tenant_id"), authority.get("principal_id")
        if not isinstance(tenant_id, str) or not isinstance(principal_id, str):
            return _empty(seed_ids or [], selected, "identity_required")
        resolved_ids = list(seed_ids or [])
        try:
            resolved_ids.extend(encode_node_id(
                item["kind"], tenant_id, principal_id, item["local_id"],
            ) for item in (seed_refs or []))
        except (KeyError, TypeError, ValueError):
            return _empty([], selected, "invalid_or_foreign_seed")
        request = NeighborhoodRequest(
            seed_ids=tuple(resolved_ids), tenant_id=tenant_id,
            principal_id=principal_id,
            relationship_types=tuple(relationship_types or ()),
            direction=direction, max_depth=max_depth,
            node_limit=node_limit, edge_limit=edge_limit,
        )
        try:
            result = runtime.get_graph(selected).get_neighborhood(request)
        except ValueError:
            return _empty(resolved_ids, selected, "invalid_or_foreign_seed")
        entities = [EntityData(
            id=item.id, type=item.type, properties=item.properties,
            labels=item.labels,
        ) for item in result.entities]
        relationships = [RelationshipData(
            id=item.id, type=item.type, source_id=item.source_id,
            target_id=item.target_id, properties=item.properties,
        ) for item in result.relationships]
        return NeighborhoodData(
            seed_ids=resolved_ids, entities=entities, relationships=relationships,
            entity_count=len(entities), relationship_count=len(relationships),
            depth_reached=result.depth_reached,
            nodes_truncated=result.nodes_truncated,
            edges_truncated=result.edges_truncated, backend=selected,
        )


def _authority(explicit: dict | None) -> dict[str, Any]:
    value = {key: item for key, item in dict(explicit or {}).items() if item is not None}
    value.update(get_envelope() or {})
    return value


def _empty(
    seed_ids: list[str], backend: str, error: str,
    available: list[str] | None = None,
) -> NeighborhoodData:
    return NeighborhoodData(
        seed_ids=seed_ids, entities=[], relationships=[], entity_count=0,
        relationship_count=0, depth_reached=0, nodes_truncated=False,
        edges_truncated=False, backend=backend, error=error, available=available,
    )


__all__ = ["register"]
