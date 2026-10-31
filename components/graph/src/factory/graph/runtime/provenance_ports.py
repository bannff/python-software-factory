"""Protocol for durable Graph provenance projection operations."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .provenance_models import (
    DurableSourcePage,
    GraphRebuildRequest,
    GraphRebuildResult,
    GraphRelationshipWrite,
    GraphTombstone,
    GraphWriteResult,
)


class GraphProvenanceUnsupportedError(RuntimeError):
    """The selected graph backend does not expose provenance projection."""

    code = "unsupported_backend"

    def __init__(self, backend: str) -> None:
        self.backend = backend
        super().__init__(f"Graph provenance is unsupported for backend '{backend}'")


@runtime_checkable
class GraphProvenancePort(Protocol):
    """Durable, deterministic relationship projection capabilities.

    ``@runtime_checkable`` verifies method NAMES exist only, not
    signatures or behavior (dev-principles.md SDK-First precedent). The
    ``neo4j``/Neptune-style backends intentionally implement all three
    methods here but raise ``GraphProvenanceUnsupportedError`` at call
    time — they legitimately pass ``isinstance`` against this Protocol
    (the repo's established idiom for "adapter narrower than full
    contract": implement + reject-stub, not omit). ``GraphRuntime.
    provenance_backends()`` remains the data-driven allowlist for
    callers that need to know which backends actually support these
    calls before invoking them.
    """

    def write_relationship(self, write: GraphRelationshipWrite) -> GraphWriteResult:
        """Create, match, conflict, or reject a relationship write."""
        ...

    def tombstone_relationship(self, tombstone: GraphTombstone) -> GraphWriteResult:
        """Record a source tombstone and remove matching live edges."""
        ...

    def rebuild(
        self, request: GraphRebuildRequest, page: DurableSourcePage,
    ) -> GraphRebuildResult:
        """Replay one immutable source page from a validated checkpoint."""
        ...


__all__ = ["GraphProvenancePort", "GraphProvenanceUnsupportedError"]
