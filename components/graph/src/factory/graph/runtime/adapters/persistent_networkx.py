"""Persistent NetworkX adapter backed by integrity-checked storage snapshots."""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable, TypeVar

from ..ports import Entity, GraphHealth, KnowledgeGraph, Relationship
from ..provenance_models import (
    DurableSourcePage, GraphRebuildRequest, GraphRebuildResult,
    GraphRelationshipWrite, GraphTombstone, GraphWriteResult,
)
from . import networkx_provenance
from .networkx_adapter import NetworkXGraph
from .persistent_networkx_lock import cross_process_lock
from .persistent_networkx_snapshot import (
    _SNAPSHOT_VERSION, DecodedSnapshot, decode_snapshot, encode_snapshot,
    restore_graph, serialize_graph,
)

_SNAPSHOT_KEY = "graph/knowledge_graph_snapshot.json"
_SNAPSHOT_LOCK = RLock()
_Result = TypeVar("_Result")


class GraphPersistenceError(RuntimeError):
    """A graph mutation could not be durably committed."""


class UnsupportedBlobStoreError(GraphPersistenceError):
    """The configured blob store cannot provide safe snapshot mutation."""


def _require_local_snapshot_store(store: Any) -> None:
    """Fail closed until the shared BlobStore exposes a CAS write contract."""
    if getattr(store, "_root", None) is None:
        raise UnsupportedBlobStoreError(
            "persistent NetworkX mutations require a local advisory lock or BlobStore CAS"
        )


def _get_blob_store() -> Any:
    """Resolve the storage blob port through the platform service seam."""
    try:
        from factory.mcp_utils.interface import get_service

        store = get_service("blob_store")
        if store is not None:
            return store
    except Exception:
        pass
    from factory.storage.interface import get_blob_store

    return get_blob_store("local")


class PersistentNetworkXGraph(NetworkXGraph):
    """NetworkX graph whose successful mutations are durable local snapshots.

    A process-wide lock plus an advisory filesystem lock serializes local
    adapter instances and processes. The shared BlobStore port has no CAS;
    non-filesystem stores therefore remain a documented single-writer boundary.
    """

    def __init__(self, snapshot_key: str = _SNAPSHOT_KEY, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._snapshot_key = snapshot_key
        self._blob_store: Any = None
        self._load_snapshot_or_start_fresh()

    def _get_blob_store(self) -> Any:
        if self._blob_store is None:
            self._blob_store = _get_blob_store()
        return self._blob_store

    def _load_snapshot(self) -> None:
        """Replace in-memory state from a valid committed snapshot when present."""
        store = self._get_blob_store()
        if not store.exists(self._snapshot_key):
            return
        data, _meta = store.get(self._snapshot_key)
        self._restore_from_node_link(decode_snapshot(data))

    def _load_snapshot_or_start_fresh(self) -> None:
        """Load the committed snapshot, allowing only an absent snapshot to start fresh."""
        try:
            self._load_snapshot()
        except FileNotFoundError:
            return

    def _persist_snapshot(self) -> None:
        data = encode_snapshot(self._get_graph())
        self._get_blob_store().put(
            self._snapshot_key,
            data,
            content_type="application/json",
            metadata={
                "format": "networkx-node-link",
                "schema_version": str(_SNAPSHOT_VERSION),
            },
        )

    def _mutate(self, operation: Callable[[], _Result]) -> _Result:
        """Apply one mutation only if its complete snapshot is durably written."""
        store = self._get_blob_store()
        _require_local_snapshot_store(store)
        with _SNAPSHOT_LOCK, cross_process_lock(store, self._snapshot_key):
            self._load_snapshot_or_start_fresh()
            before = self._to_node_link()
            try:
                result = operation()
                self._persist_snapshot()
                return result
            except Exception as exc:
                self._restore_from_node_link(before)
                raise GraphPersistenceError("graph mutation was not persisted") from exc

    def _to_node_link(self) -> DecodedSnapshot:
        """Capture rollback state with collision-proof node attributes."""
        return DecodedSnapshot(
            graph=serialize_graph(self._get_graph()), schema_version=_SNAPSHOT_VERSION,
        )

    def _restore_from_node_link(self, snapshot: DecodedSnapshot) -> None:
        self._graph = restore_graph(snapshot)

    def add_entity(self, entity: Entity) -> Entity:
        return self._mutate(lambda: super(PersistentNetworkXGraph, self).add_entity(entity))

    def update_entity(self, entity: Entity) -> Entity:
        return self._mutate(lambda: super(PersistentNetworkXGraph, self).update_entity(entity))

    def delete_entity(self, entity_id: str) -> bool:
        return self._mutate(lambda: super(PersistentNetworkXGraph, self).delete_entity(entity_id))

    def add_relationship(self, relationship: Relationship) -> Relationship:
        return self._mutate(lambda: super(PersistentNetworkXGraph, self).add_relationship(relationship))

    def delete_relationship(self, relationship_id: str) -> bool:
        return self._mutate(lambda: super(PersistentNetworkXGraph, self).delete_relationship(relationship_id))

    def set_finding_state(self, finding_id: str, state: str) -> bool:
        return self._mutate(lambda: super(PersistentNetworkXGraph, self).set_finding_state(finding_id, state))

    def import_snapshot(self, data: bytes) -> None:
        """Same as ``NetworkXGraph.import_snapshot`` but durably persisted
        (row 48 — owner direction 2026-09-16), so the imported graph
        survives a restart instead of only living until the process ends."""
        self._mutate(lambda: super(PersistentNetworkXGraph, self).import_snapshot(data))

    def write_relationship(self, write: GraphRelationshipWrite) -> GraphWriteResult:
        return self._mutate(lambda: networkx_provenance.write_relationship(self, write))

    def tombstone_relationship(self, tombstone: GraphTombstone) -> GraphWriteResult:
        return self._mutate(lambda: networkx_provenance.tombstone_relationship(self, tombstone))

    def rebuild(
        self, request: GraphRebuildRequest, page: DurableSourcePage,
    ) -> GraphRebuildResult:
        return self._mutate(lambda: networkx_provenance.rebuild(self, request, page))

    def health_check(self) -> GraphHealth:
        health = super().health_check()
        health.backend = "persistent_networkx"
        return health


# Verify protocol compliance (@runtime_checkable checks method names only).
# issubclass, not isinstance, since __init__ has real blob-storage side
# effects (loads a snapshot) that shouldn't fire at module import time.
assert issubclass(PersistentNetworkXGraph, KnowledgeGraph)
