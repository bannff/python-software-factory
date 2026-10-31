"""Flat MCP ingress models for Graph provenance operations."""
from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from ..runtime.provenance_models import (
    DurableSourcePage, GraphProvenanceModel, GraphRelationshipWrite,
    GraphRebuildCheckpoint, GraphRebuildResult, GraphSourceRecord,
    GraphTombstone, GraphWriteResult,
)


class GraphWriteInput(GraphRelationshipWrite):
    backend: str = ""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GraphTombstoneInput(GraphTombstone):
    backend: str = ""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @field_validator("deleted_at", mode="before")
    @classmethod
    def parse_wire_timestamp(cls, value: object) -> object:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


class GraphRebuildInput(GraphProvenanceModel):
    source_system: str
    snapshot_id: str
    snapshot_digest: str
    ordinal_start: int = Field(ge=0)
    records: list[GraphSourceRecord] = Field(max_length=256)
    next_cursor: str | None = None
    cursor: str | None = None
    checkpoint: GraphRebuildCheckpoint | None = None
    backend: str = ""


__all__ = [
    "DurableSourcePage", "GraphRebuildInput", "GraphRebuildResult",
    "GraphTombstoneInput", "GraphWriteInput", "GraphWriteResult",
]
