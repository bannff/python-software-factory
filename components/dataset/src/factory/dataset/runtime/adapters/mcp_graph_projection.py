"""Dataset-owned Graph projection adapters; production crosses named MCP tools."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from ..ports import GraphEntityResult, GraphRelationshipResult


def _exact_payload(payload: Any, expected: dict[str, Any], tool_name: str) -> dict[str, Any]:
    """Verify Dataset's expected Graph mutation payload."""
    if not isinstance(payload, dict):
        raise RuntimeError(f"{tool_name} returned non-object success data")
    if set(payload) != set(expected) or payload != expected:
        raise RuntimeError(f"{tool_name} returned a partial or mismatched mutation")
    return payload


def _exact_result(result: Any, expected: dict[str, Any], tool_name: str) -> dict[str, Any]:
    """Unwrap and verify Graph's typed successful mutation result."""
    if not isinstance(result, dict):
        raise RuntimeError(f"{tool_name} returned a non-object result")
    envelope_keys = {"schema_version", "ok", "data", "error", "idempotency_key"}
    if set(result) != envelope_keys:
        raise RuntimeError(
            f"{tool_name} returned malformed envelope keys: "
            f"expected {sorted(envelope_keys)}, got {sorted(result)}"
        )
    if result["schema_version"] != "v1" or result["ok"] is not True or result["error"] is not None:
        raise RuntimeError(f"{tool_name} returned an unsuccessful result")
    return _exact_payload(result["data"], expected, tool_name)


class McpGraphProjectionAdapter:
    """Persist Graph entities/relationships through the production invoker."""

    def __init__(self, invoker: Any | None = None, backend: str = "") -> None:
        self._invoker = invoker
        self._backend = backend

    def _invoke(self, name: str, expected: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        invoker = self._invoker
        if invoker is None:
            from factory.mcp_utils.interface import get_service
            invoker = get_service("tool_invoker")
        if invoker is None:
            raise RuntimeError("Graph projection requires the named MCP tool_invoker service")
        try:
            result = invoker(name, **kwargs)
        except Exception as exc:
            raise RuntimeError(f"{name} transport failure: {exc}") from exc
        return _exact_result(result, expected, name)

    def add_entity(
        self, entity_id: str, entity_type: str, properties: dict[str, Any],
    ) -> GraphEntityResult:
        expected = {
            "id": entity_id, "type": entity_type,
            "properties": properties, "labels": [],
        }
        return cast(GraphEntityResult, self._invoke(
            "graph_graph_add_entity", expected, entity_id=entity_id,
            entity_type=entity_type, properties=properties, backend=self._backend,
        ))

    def add_relationship(
        self, relationship_id: str, relationship_type: str,
        source_id: str, target_id: str, properties: dict[str, Any],
    ) -> GraphRelationshipResult:
        expected = {
            "id": relationship_id, "type": relationship_type,
            "source_id": source_id, "target_id": target_id,
            "properties": properties,
        }
        return cast(GraphRelationshipResult, self._invoke(
            "graph_graph_add_relationship", expected,
            relationship_id=relationship_id, relationship_type=relationship_type,
            source_id=source_id, target_id=target_id,
            properties=properties, backend=self._backend,
        ))


@dataclass(frozen=True)
class _EntityPayload:
    id: str
    type: str
    properties: dict[str, Any]
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RelationshipPayload:
    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any]


class ObjectGraphProjectionAdapter:
    """Constructor-injected test adapter without importing the Graph brick."""

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    def add_entity(
        self, entity_id: str, entity_type: str, properties: dict[str, Any],
    ) -> GraphEntityResult:
        result = self.graph.add_entity(_EntityPayload(entity_id, entity_type, properties))
        raw = {"id": result.id, "type": result.type,
               "properties": result.properties, "labels": list(result.labels)}
        expected = {"id": entity_id, "type": entity_type,
                    "properties": properties, "labels": []}
        return cast(GraphEntityResult, _exact_payload(raw, expected, "graph.add_entity"))

    def add_relationship(
        self, relationship_id: str, relationship_type: str,
        source_id: str, target_id: str, properties: dict[str, Any],
    ) -> GraphRelationshipResult:
        result = self.graph.add_relationship(_RelationshipPayload(
            relationship_id, relationship_type, source_id, target_id, properties,
        ))
        raw = {
            "id": result.id, "type": result.type, "source_id": result.source_id,
            "target_id": result.target_id, "properties": result.properties,
        }
        expected = {
            "id": relationship_id, "type": relationship_type,
            "source_id": source_id, "target_id": target_id,
            "properties": properties,
        }
        return cast(GraphRelationshipResult, _exact_payload(
            raw, expected, "graph.add_relationship",
        ))


__all__ = ["McpGraphProjectionAdapter", "ObjectGraphProjectionAdapter"]
