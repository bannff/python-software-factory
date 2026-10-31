"""Immutable, validated Telemetry materialization mapping contracts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import Field, PositiveInt, field_validator, model_validator

from .provenance_models import ProvenanceModel, SignalType


class MappingNodeRef(ProvenanceModel):
    mapping_id: str
    version: str


class MaterializationTarget(ProvenanceModel):
    """Immutable address used by the native structured invocation seam."""

    brick_name: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_-]*$")
    capability: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.-]+$")
    version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


class MappingEdge(ProvenanceModel):
    source: MappingNodeRef
    target: MappingNodeRef


class MaterializationMapping(ProvenanceModel):
    mapping_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    state: Literal["active"] = "active"
    accepted_signals: tuple[SignalType, ...] = Field(max_length=3)
    target_brick: str = Field(
        min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_-]*$",
    )
    target_capability: str = Field(
        min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.-]+$",
    )
    target_version: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$",
    )
    max_fan_out: PositiveInt
    output_provenance: Literal["telemetry-materialized"] = "telemetry-materialized"

    @field_validator("accepted_signals")
    @classmethod
    def canonical_signals(cls, value: tuple[SignalType, ...]) -> tuple[SignalType, ...]:
        if len(set(value)) != len(value):
            raise ValueError("accepted_signals must be unique")
        return tuple(sorted(value))


GRAPH_RELATIONSHIP_TARGET = ("graph", "graph_write_relationship", "1")


def is_graph_relationship_target(mapping: MaterializationMapping) -> bool:
    """Return whether the mapping accepts the current Graph payload contract."""
    return (
        mapping.target_brick, mapping.target_capability, mapping.target_version,
    ) == GRAPH_RELATIONSHIP_TARGET


class MappingActivationRecord(ProvenanceModel):
    registry_version: str
    mappings: tuple[MaterializationMapping, ...]
    edges: tuple[MappingEdge, ...]
    graph_digest: str = ""
    activated_at: datetime

    @model_validator(mode="after")
    def canonicalize_and_verify_digest(self) -> "MappingActivationRecord":
        mappings = tuple(sorted(self.mappings, key=lambda item: (item.mapping_id, item.version)))
        edges = tuple(sorted(self.edges, key=lambda edge: (
            edge.source.mapping_id, edge.source.version,
            edge.target.mapping_id, edge.target.version,
        )))
        keys = {(item.mapping_id, item.version) for item in mappings}
        for edge in edges:
            if (edge.source.mapping_id, edge.source.version) not in keys or (edge.target.mapping_id, edge.target.version) not in keys:
                raise ValueError("mapping edge references an unknown mapping")
        for item in mappings:
            target = item.target_brick.lower().replace("factory.", "")
            if target.split(".", 1)[0] in {"telemetry", "agent", "workflow"}:
                raise ValueError("mapping target is not an allowed capability brick")
            if not is_graph_relationship_target(item):
                raise ValueError(
                    "mapping target is not compatible with GraphRelationshipPayload"
                )
        adjacency: dict[tuple[str, str], list[tuple[str, str]]] = {key: [] for key in keys}
        for edge in edges:
            adjacency[(edge.source.mapping_id, edge.source.version)].append(
                (edge.target.mapping_id, edge.target.version)
            )
        visiting: set[tuple[str, str]] = set()
        visited: set[tuple[str, str]] = set()

        def visit(node: tuple[str, str]) -> None:
            if node in visiting:
                raise ValueError("mapping activation graph must be acyclic")
            if node in visited:
                return
            visiting.add(node)
            for target in adjacency[node]:
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in keys:
            visit(node)
        canonical = {
            "registry_version": self.registry_version,
            "mappings": [item.model_dump(mode="json") for item in mappings],
            "edges": [edge.model_dump(mode="json") for edge in edges],
        }
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self.graph_digest not in ("", digest):
            raise ValueError("mapping activation graph_digest does not match canonical registry")
        object.__setattr__(self, "mappings", mappings)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "graph_digest", digest)
        return self


__all__ = [
    "MappingActivationRecord", "MappingEdge", "MappingNodeRef",
    "MaterializationMapping", "MaterializationTarget", "GRAPH_RELATIONSHIP_TARGET",
    "is_graph_relationship_target",
]
