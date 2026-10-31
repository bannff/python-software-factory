"""Explicit provenance capability gate for the Neo4j graph adapter."""
from __future__ import annotations

from typing import NoReturn

from ..provenance_models import (
    DurableSourcePage, GraphRebuildRequest, GraphRebuildResult,
    GraphRelationshipWrite, GraphTombstone, GraphWriteResult,
)
from ..provenance_ports import GraphProvenanceUnsupportedError


class Neo4jProvenanceUnsupportedMixin:
    """Reject Graph provenance until a native transactional projection exists."""

    @staticmethod
    def _reject() -> NoReturn:
        raise GraphProvenanceUnsupportedError("neo4j")

    def write_relationship(self, write: GraphRelationshipWrite) -> GraphWriteResult:
        self._reject()

    def tombstone_relationship(self, tombstone: GraphTombstone) -> GraphWriteResult:
        self._reject()

    def rebuild(
        self, request: GraphRebuildRequest, page: DurableSourcePage,
    ) -> GraphRebuildResult:
        self._reject()

    def get_run_topology(self, run_id: str, limit: int = 200):
        from .neo4j_topology import get_run_topology
        return get_run_topology(self, run_id, limit)


__all__ = ["Neo4jProvenanceUnsupportedMixin"]
