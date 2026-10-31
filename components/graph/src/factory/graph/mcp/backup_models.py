"""Typed contracts for whole-graph export/import (row 48).

Owner direction 2026-09-16: "simple export/import of the whole graph to
one file; no staged-restore-on-restart ceremony." Export/import bytes are
base64-encoded for the JSON wire — the underlying file is still one
portable, checksummed JSON document once decoded.

**Paged, not one inline blob (fixed 2026-09-16):** the owner's real graph
serializes to ~38.5 MB raw / ~51.4 MB base64 — over 3x the typed-egress
boundary's 16 MiB per-call cap (`factory.mcp_utils.runtime.typed_egress`).
A single-call inline transfer would ALWAYS fail past ~11 MB raw, not just
occasionally — this is a systemic size bug, not an edge case. Fixed by
paging the base64 string into bounded chunks the caller fetches across
multiple calls and concatenates client-side, staying entirely inside the
existing MCP tool contract (no new HTTP download route, no artifact-store
dependency — smallest blast radius for "the simple version").
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Each page's base64 chunk is capped well under the 16 MiB egress limit,
# leaving headroom for the rest of the ToolResult envelope (schema_version,
# ok, ids, etc.) and this contract's own other fields.
PAGE_CHUNK_CHARS = 8 * 1024 * 1024  # 8 MiB of base64 chars per page


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GraphExportInput(_DTO):
    backend: str = "persistent_networkx"
    page: int = Field(default=0, ge=0)


class GraphExportOutput(_DTO):
    backend: str
    supported: bool = True
    data_base64: str
    byte_size: int
    page: int = 0
    page_count: int = 1
    done: bool = True


class GraphImportBeginInput(_DTO):
    backend: str = "persistent_networkx"
    total_pages: int = Field(ge=1)


class GraphImportBeginOutput(_DTO):
    import_id: str


class GraphImportPageInput(_DTO):
    import_id: str = Field(min_length=1)
    page: int = Field(ge=0)
    data_base64: str = Field(min_length=1)


class GraphImportPageOutput(_DTO):
    import_id: str
    received_pages: int
    total_pages: int
    imported: bool = False
    error: str | None = None


__all__ = [
    "PAGE_CHUNK_CHARS",
    "GraphExportInput", "GraphExportOutput",
    "GraphImportBeginInput", "GraphImportBeginOutput",
    "GraphImportPageInput", "GraphImportPageOutput",
]
