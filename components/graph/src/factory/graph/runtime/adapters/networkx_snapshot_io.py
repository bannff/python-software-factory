"""Whole-graph export/import as one portable file (row 48).

Owner direction 2026-09-16: "simple export/import of the whole graph to one
file; no staged-restore-on-restart ceremony" — a deliberately smaller scope
than upstream's stage-then-restart-to-apply backup flow. Thin wrapper over
the same checksummed envelope ``persistent_networkx`` already durably
writes on every mutation (``persistent_networkx_snapshot.py``), so an
export is always a byte-identical twin of what a restart would reload.

Split out of ``networkx_adapter.py`` to keep that file under the 200 LOC
ceiling — same doctrine as ``networkx_runs.py``'s delegation split.
"""
from __future__ import annotations

from typing import Any

from .persistent_networkx_snapshot import decode_snapshot, encode_snapshot, restore_graph


def export_snapshot(graph: Any) -> bytes:
    return encode_snapshot(graph)


def import_snapshot(data: bytes) -> Any:
    """Decode and restore a graph object. Raises ``SnapshotIntegrityError``
    on a corrupt/foreign file — the caller assigns the result, never
    mutates in place, so a failed import leaves the prior graph untouched."""
    return restore_graph(decode_snapshot(data))


__all__ = ["export_snapshot", "import_snapshot"]
