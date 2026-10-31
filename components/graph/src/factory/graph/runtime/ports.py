"""Abstract ports for graph brick.

Ports define what capabilities the knowledge graph needs, not how
they're implemented. For semantic graphs, not raw storage (storage brick).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .entity_contract import RESERVED_NODE_ATTRS, normalize_entity_properties
from .models import TaxonomyEdgeSpec
from .neighbor_limits import DEFAULT_NEIGHBOR_LIMIT
from .neighborhood import NeighborhoodPort
from .provenance_ports import GraphProvenancePort, GraphProvenanceUnsupportedError


@dataclass
class GraphHealth:
    """Health status for a graph backend."""
    healthy: bool
    backend: str
    node_count: int = 0
    edge_count: int = 0
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class Entity:
    """A node/entity in the knowledge graph.

    ``type``/``labels`` are canonical node attributes. Same-named keys inside
    ``properties`` are contract-relocated to ``prop_type``/``prop_labels`` by
    ``normalize_entity_properties`` so the entity round-trips identically on
    every backend (contract, not an adapter quirk).
    """
    id: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    """An edge/relationship in the knowledge graph."""
    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphPath:
    """A path through the graph."""
    entities: list[Entity]
    relationships: list[Relationship]
    length: int = 0


@dataclass
class QueryResult:
    """Result from a graph query."""
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    paths: list[GraphPath] = field(default_factory=list)
    raw: Any = None


@runtime_checkable
class KnowledgeGraph(GraphProvenancePort, NeighborhoodPort, Protocol):
    """Port: Knowledge graph for semantic relationships.

    ``@runtime_checkable`` verifies method NAMES exist only (not
    signatures/behavior) — see ``GraphProvenancePort``'s docstring for
    the neo4j-narrower-contract caveat this inherits.
    """

    def add_entity(self, entity: Entity) -> Entity:
        """Add an entity. Contract: caller ``properties`` keys ``type``/
        ``labels`` are preserved under ``prop_type``/``prop_labels`` (canonical
        ``entity.type``/``entity.labels`` own the real attributes). All
        adapters write through ``normalize_entity_properties``."""
        ...

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        ...

    def update_entity(self, entity: Entity) -> Entity:
        """Update an entity's properties."""
        ...

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relationships."""
        ...

    def add_relationship(self, relationship: Relationship) -> Relationship:
        """Add a relationship between entities."""
        ...

    def get_relationship(self, relationship_id: str) -> Relationship | None:
        """Get a relationship by ID."""
        ...

    def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        ...

    def get_neighbors(
        self,
        entity_id: str,
        relationship_type: str | None = None,
        direction: str = "both",
        limit: int = DEFAULT_NEIGHBOR_LIMIT,
    ) -> list[Entity]:
        """Get at most ``limit`` neighboring entities."""
        ...

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> GraphPath | None:
        """Find shortest path between entities."""
        ...

    def find_entities(
        self,
        entity_type: str | None = None,
        properties: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """Find entities by type and/or properties."""
        ...

    def health_check(self) -> GraphHealth:
        """Check graph health."""
        ...

    # --- Typed reads (bd j1lb / c39g / epic kzd8). Each adapter implements
    # in its native dialect. ``taxonomy_edges`` (bd ecph9 / hadbi): per-call
    # one-hop joins. ``None`` = adapter default (back-compat); ``[]`` = none.

    def get_run_topology(self, run_id: str, limit: int = 200) -> QueryResult:
        """Return bounded persisted seeds, incident edges, and one-hop boundaries."""
        ...

    def get_findings_for_run(
        self, run_id: str, app: str = "", limit: int = 50,
        taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
    ) -> QueryResult:
        """Finding rows for a run, optionally taxonomy-joined. Rows =
        Finding props + one col per edge spec (``None`` on miss);
        ``taxonomy_edges=None`` uses adapter defaults (security CWE/OCSF);
        sorted ``created_at`` desc."""
        ...

    def set_finding_state(self, finding_id: str, state: str) -> bool:
        """Atomically set ``Finding.state`` in one write (no RMW). Closed
        neutral set {candidate,verifying,verified,refuted}
        (bd python-factory-216ti). True iff the finding existed."""
        ...

    def count_entities_by_run(self, run_id: str, labels: list[str]) -> dict[str, int]:
        """``{label: count}`` for requested labels scoped to run_id."""
        ...

    def get_recent_findings(
        self, severity: str = "", app: str = "", run_id: str = "",
        limit: int = 50,
        taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
    ) -> QueryResult:
        """Recent Finding rows, taxonomy-joined per ``taxonomy_edges``."""
        ...

    def get_target_app(self, target_app: str, run_id: str = "") -> Entity | None:
        """TargetApp singleton by ``app``/``name``; most-recent on tie."""
        ...

    def get_tool_invocations_for_run(self, run_id: str, limit: int = 50) -> QueryResult:
        """Ordered ToolInvocation rows for a run, sorted by ``sequence``."""
        ...

    def list_recent_tool_invocations(
        self, limit: int = 100,
    ) -> QueryResult:
        """Most recent ToolInvocation rows globally, ``created_at`` desc.
        One-hop Session join adds session_* cols; excludes poll-noise."""
        ...


__all__ = [
    "GraphHealth", "Entity", "Relationship", "GraphPath", "QueryResult",
    "KnowledgeGraph", "GraphProvenancePort", "GraphProvenanceUnsupportedError", "TaxonomyEdgeSpec", "RESERVED_NODE_ATTRS", "normalize_entity_properties",
]
