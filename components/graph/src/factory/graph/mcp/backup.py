"""Whole-graph export/import MCP tools (row 48).

Owner direction 2026-09-16: "simple export/import of the whole graph to
one file; no staged-restore-on-restart ceremony" — deliberately smaller
scope than upstream's stage-then-restart-to-apply backup flow. Applies
immediately, in-process, on the SAME shared graph the memory/kb bricks
both write into (M7.7 unified graph), not a per-brick backup.

**Paged (fixed 2026-09-16):** a whole-graph snapshot easily exceeds the
16 MiB typed-egress cap (the owner's real graph is ~51 MB base64) — see
`backup_models.py`'s module docstring for the full root-cause writeup.
Export slices the base64 string into bounded pages the caller re-fetches
by page number; import accumulates pages server-side under a short-lived
`import_id` and applies only once every page has arrived.
"""
from __future__ import annotations

import base64
import secrets
import time
from typing import TYPE_CHECKING, Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.adapters.persistent_networkx_snapshot import SnapshotIntegrityError
from .backup_models import (
    PAGE_CHUNK_CHARS,
    GraphExportInput, GraphExportOutput,
    GraphImportBeginInput, GraphImportBeginOutput,
    GraphImportPageInput, GraphImportPageOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime

# Short-lived, in-process export cache keyed by backend: avoids
# re-serializing the whole graph on every page fetch within one export.
# Entries expire after a few minutes so a client that never finishes
# paging doesn't pin memory forever.
_EXPORT_CACHE_TTL_SECONDS = 300
_export_cache: dict[str, tuple[float, str]] = {}  # backend -> (expires_at, base64_data)

# In-process import-session accumulator, keyed by a random import_id.
# Same TTL/eviction rationale as the export cache.
_IMPORT_SESSION_TTL_SECONDS = 300
_import_sessions: dict[str, dict[str, Any]] = {}


def _evict_expired(cache: dict[str, Any], now: float, expiry_key: Callable[[Any], float]) -> None:
    expired = [k for k, v in cache.items() if expiry_key(v) < now]
    for k in expired:
        del cache[k]


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    @typed_tool(mcp)
    @operational(input_model=GraphExportInput, output_model=GraphExportOutput)
    def graph_export(backend: str = "persistent_networkx", page: int = 0) -> ToolResult[GraphExportOutput]:
        now = time.monotonic()
        _evict_expired(_export_cache, now, lambda v: v[0])

        cached = _export_cache.get(backend)
        if cached is None:
            graph = get_runtime().get_graph(backend)
            export = getattr(graph, "export_snapshot", None)
            if not callable(export):
                return GraphExportOutput(
                    backend=backend, supported=False, data_base64="", byte_size=0,
                    page=0, page_count=1, done=True,
                )
            raw = export()
            encoded = base64.b64encode(raw).decode("ascii")
            _export_cache[backend] = (now + _EXPORT_CACHE_TTL_SECONDS, encoded)
            cached = _export_cache[backend]
        else:
            raw = None  # byte_size below comes from the cached encoded string's decode length
        encoded = cached[1]

        page_count = max(1, -(-len(encoded) // PAGE_CHUNK_CHARS))  # ceil div
        if page >= page_count:
            return GraphExportOutput(
                backend=backend, data_base64="", byte_size=0,
                page=page, page_count=page_count, done=True,
            )
        start = page * PAGE_CHUNK_CHARS
        chunk = encoded[start:start + PAGE_CHUNK_CHARS]
        is_last = (page == page_count - 1)
        byte_size = len(raw) if raw is not None else 0
        return GraphExportOutput(
            backend=backend, data_base64=chunk, byte_size=byte_size,
            page=page, page_count=page_count, done=is_last,
        )

    @typed_tool(mcp)
    @operational(input_model=GraphImportBeginInput, output_model=GraphImportBeginOutput)
    def graph_import_begin(backend: str = "persistent_networkx", total_pages: int = 1) -> ToolResult[GraphImportBeginOutput]:
        now = time.monotonic()
        _evict_expired(_import_sessions, now, lambda v: v["expires_at"])
        import_id = secrets.token_urlsafe(16)
        _import_sessions[import_id] = {
            "backend": backend, "total_pages": total_pages, "pages": {},
            "expires_at": now + _IMPORT_SESSION_TTL_SECONDS,
        }
        return GraphImportBeginOutput(import_id=import_id)

    @typed_tool(mcp)
    @operational(input_model=GraphImportPageInput, output_model=GraphImportPageOutput)
    def graph_import_page(import_id: str, page: int, data_base64: str) -> ToolResult[GraphImportPageOutput]:
        now = time.monotonic()
        _evict_expired(_import_sessions, now, lambda v: v["expires_at"])
        session = _import_sessions.get(import_id)
        if session is None:
            return GraphImportPageOutput(
                import_id=import_id, received_pages=0, total_pages=0,
                imported=False, error="unknown_or_expired_import_id",
            )
        session["pages"][page] = data_base64
        total_pages = session["total_pages"]
        received = len(session["pages"])
        if received < total_pages:
            return GraphImportPageOutput(
                import_id=import_id, received_pages=received, total_pages=total_pages,
                imported=False,
            )

        # All pages arrived — assemble, decode, and apply.
        try:
            ordered = [session["pages"][i] for i in range(total_pages)]
        except KeyError:
            return GraphImportPageOutput(
                import_id=import_id, received_pages=received, total_pages=total_pages,
                imported=False, error="missing_page",
            )
        full_base64 = "".join(ordered)
        try:
            data = base64.b64decode(full_base64, validate=True)
        except (ValueError, TypeError):
            del _import_sessions[import_id]
            return GraphImportPageOutput(
                import_id=import_id, received_pages=received, total_pages=total_pages,
                imported=False, error="invalid_base64",
            )
        backend = session["backend"]
        graph = get_runtime().get_graph(backend)
        importer = getattr(graph, "import_snapshot", None)
        if not callable(importer):
            del _import_sessions[import_id]
            return GraphImportPageOutput(
                import_id=import_id, received_pages=received, total_pages=total_pages,
                imported=False, error="backend_not_supported",
            )
        try:
            importer(data)
        except SnapshotIntegrityError as exc:
            del _import_sessions[import_id]
            return GraphImportPageOutput(
                import_id=import_id, received_pages=received, total_pages=total_pages,
                imported=False, error=str(exc),
            )
        del _import_sessions[import_id]
        _export_cache.pop(backend, None)  # the graph changed — stale export cache is now wrong
        return GraphImportPageOutput(
            import_id=import_id, received_pages=received, total_pages=total_pages,
            imported=True,
        )


__all__ = ["register"]
