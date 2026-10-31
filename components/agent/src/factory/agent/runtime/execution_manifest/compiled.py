"""Internal preparation graph representation."""
from __future__ import annotations

from dataclasses import dataclass

from .nodes import ManifestNode


@dataclass(frozen=True)
class CompiledEdge:
    source: str
    target: str
    condition: str | None = None


@dataclass(frozen=True)
class CompiledGraph:
    graph_id: str
    name: str
    description: str
    nodes: tuple[ManifestNode, ...]
    edges: tuple[CompiledEdge, ...]
    entries: tuple[str, ...]
    max_node_executions: int | None
    max_cycles: int | None
    execution_timeout: float
    node_timeout: float

    @property
    def terminals(self) -> tuple[str, ...]:
        sources = {edge.source for edge in self.edges}
        return tuple(node.id for node in self.nodes if node.id not in sources)


__all__ = ["CompiledEdge", "CompiledGraph"]
