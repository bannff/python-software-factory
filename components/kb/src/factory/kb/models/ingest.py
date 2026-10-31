"""Pydantic models for the stable v1 KB ingest MCP contract.

FastMCP/Strands keep a **flat kwargs** tool schema (nested ``request: Model``
breaks flat tool-call args). Field constraints are therefore declared on the
tool signature via ``Field(...)`` and mirrored here for boundary validation.
Breaking wire changes require a new, parallel versioned MCP tool; they cannot
rely on a decorator migration because FastMCP validates arguments first.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class KbGraphReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: str = Field(min_length=1, max_length=32)
    local_id: str = Field(min_length=1, max_length=128)
    entity_type: str = Field(min_length=1, max_length=64)
    relation_type: str = Field(min_length=1, max_length=64)


class KbIngestRequest(BaseModel):
    """Ingress model for the stable ``kb.ingest`` v1 contract."""

    schema_version: Literal["v1"] = "v1"
    content: str = Field(..., min_length=1)
    document_id: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[a-z0-9_\-]+$",
    )
    metadata: dict[str, Any] | None = None
    source: str | None = None
    extract_entities: bool | None = None
    graph_references: list[KbGraphReference] = Field(default_factory=list, max_length=32)
    tenant_id: str | None = None
    principal_id: str | None = None
    idempotency_key: str | None = None


class KbIngestResult(BaseModel):
    """Egress payload nested under ``ToolResult.data`` for ``kb.ingest``."""

    schema_version: Literal["v1"] = "v1"
    document_id: str
    status: str
    extraction: dict[str, Any] | None = None


__all__ = ["KbGraphReference", "KbIngestRequest", "KbIngestResult"]
