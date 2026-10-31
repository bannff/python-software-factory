"""Top-level ExecutionManifestV1 contract."""
from __future__ import annotations

from typing import Literal

from pydantic import JsonValue, model_validator

from .base import DigestValue, FrozenModel
from .descriptors import ConditionDescriptor, HookDescriptor
from .nodes import ManifestNode


class ManifestOrigin(FrozenModel):
    kind: Literal["registered", "dynamic"]
    source_id: str


class GraphLimits(FrozenModel):
    max_node_executions: int
    execution_timeout: float
    node_timeout: float


class EdgeManifest(FrozenModel):
    source: str
    target: str
    condition: ConditionDescriptor | None
    predecessors: tuple[str, ...]


class InvocationManifest(FrozenModel):
    task: str
    context: dict[str, JsonValue]
    invocation_state: dict[str, JsonValue]


class ProvenanceRecord(FrozenModel):
    kind: str
    identity: str
    digest: DigestValue | None


class ExecutionManifestV1(FrozenModel):
    schema_name: Literal["agent-execution-manifest"] = "agent-execution-manifest"
    schema_version: Literal["1"] = "1"
    origin: ManifestOrigin
    graph_id: str
    graph_name: str
    description: str
    nodes: tuple[ManifestNode, ...]
    edges: tuple[EdgeManifest, ...]
    entry_points: tuple[str, ...]
    limits: GraphLimits
    hooks: tuple[HookDescriptor, ...]
    invocation: InvocationManifest
    sdk_name: Literal["langgraph"] = "langgraph"
    sdk_version: str
    assembler_version: Literal["1"] = "1"
    provenance: tuple[ProvenanceRecord, ...]
    digest: DigestValue | None = None

    @model_validator(mode="after")
    def _topology(self) -> "ExecutionManifestV1":
        ids = [node.id for node in self.nodes]
        known = set(ids)
        if len(ids) != len(known) or not ids:
            raise ValueError("manifest node ids must be non-empty and unique")
        if not self.entry_points or len(self.entry_points) != len(set(self.entry_points)):
            raise ValueError("entry points must be ordered, non-empty, and unique")
        if not set(self.entry_points) <= known:
            raise ValueError("entry point references unknown node")
        pairs: set[tuple[str, str]] = set()
        for edge in self.edges:
            pair = (edge.source, edge.target)
            if pair in pairs or edge.source not in known or edge.target not in known:
                raise ValueError("edge is duplicate or references unknown node")
            if set(edge.predecessors) - known:
                raise ValueError("condition predecessors reference unknown node")
            pairs.add(pair)
        return self


__all__ = [
    "EdgeManifest", "ExecutionManifestV1", "GraphLimits", "InvocationManifest",
    "ManifestOrigin", "ProvenanceRecord",
]
