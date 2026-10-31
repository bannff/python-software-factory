"""Strict contracts for the durable, domain-neutral Graph projection."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, field_validator

from factory.mcp_utils.interface import is_bounded_json


VisibilityScope = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class GraphProvenanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GraphRelationshipWrite(GraphProvenanceModel):
    source_system: str = Field(min_length=1, max_length=128)
    source_identity: str = Field(min_length=1, max_length=256)
    source_digest: str = Field(min_length=1, max_length=256)
    relation_type: str = Field(min_length=1, max_length=128)
    source_endpoint: str = Field(min_length=1, max_length=512)
    target_endpoint: str = Field(min_length=1, max_length=512)
    source_ref: str = Field(min_length=1, max_length=512)
    visibility: VisibilityScope
    browse_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("browse_metadata")
    @classmethod
    def bounded_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not is_bounded_json(value):
            raise ValueError("browse_metadata exceeds bounded JSON limits")
        return value


class GraphWriteResult(GraphProvenanceModel):
    relationship_id: str
    status: Literal["created", "matched", "conflict", "tombstoned"]
    immutable_digest: str
    conflict_ref: str | None = None


class GraphRebuildCheckpoint(GraphProvenanceModel):
    version: Literal["v1"] = "v1"
    snapshot_id: str = Field(min_length=1, max_length=256)
    snapshot_digest: str = Field(min_length=1, max_length=256)
    last_ordinal: int = Field(ge=-1)
    cursor: str | None = Field(default=None, max_length=512)
    checkpoint_digest: str = Field(min_length=1, max_length=128)
    page_ordinal_start: int | None = Field(default=None, ge=0)
    page_digest: str | None = Field(default=None, min_length=1, max_length=128)


class GraphTombstone(GraphProvenanceModel):
    source_system: str = Field(min_length=1, max_length=128)
    source_identity: str = Field(min_length=1, max_length=256)
    source_digest: str = Field(min_length=1, max_length=256)
    deleted_at: datetime

    @field_validator("deleted_at", mode="before")
    @classmethod
    def parse_wire_timestamp(cls, value: object) -> object:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


GraphSourceRecord = GraphRelationshipWrite | GraphTombstone


class DurableSourcePage(GraphProvenanceModel):
    snapshot_id: str = Field(min_length=1, max_length=256)
    snapshot_digest: str = Field(min_length=1, max_length=256)
    ordinal_start: int = Field(ge=0)
    records: tuple[GraphSourceRecord, ...]
    next_cursor: str | None = Field(default=None, max_length=512)


class GraphRebuildRequest(GraphProvenanceModel):
    source_system: str = Field(min_length=1, max_length=128)
    snapshot_id: str = Field(min_length=1, max_length=256)
    snapshot_digest: str = Field(min_length=1, max_length=256)
    cursor: str | None = Field(default=None, max_length=512)
    checkpoint: GraphRebuildCheckpoint | None = None


class GraphRebuildResult(GraphProvenanceModel):
    next_cursor: str | None
    checkpoint: GraphRebuildCheckpoint
    scanned: int
    applied: int
    duplicates: int
    conflicts: int
    tombstones: int


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def relationship_id(write: GraphRelationshipWrite) -> str:
    """Return the stable identity digest; source_digest is immutable content."""
    identity = {
        "source_system": write.source_system,
        "source_identity": write.source_identity,
        "relation_type": write.relation_type,
        "source_endpoint": write.source_endpoint,
        "target_endpoint": write.target_endpoint,
    }
    return "rel-" + hashlib.sha256(_canonical(identity).encode()).hexdigest()


def immutable_digest(write: GraphRelationshipWrite) -> str:
    return hashlib.sha256(_canonical(write.model_dump(mode="json")).encode()).hexdigest()


def source_key(source_system: str, source_identity: str) -> str:
    """Return a collision-free key for a source system and identity pair."""
    return "source-" + hashlib.sha256(
        _canonical([source_system, source_identity]).encode()
    ).hexdigest()


def tombstone_key(tombstone: GraphTombstone) -> str:
    return source_key(tombstone.source_system, tombstone.source_identity)


def source_page_digest(page: DurableSourcePage) -> str:
    """Digest the immutable page identity and ordered source records."""
    value = {
        "snapshot_id": page.snapshot_id,
        "snapshot_digest": page.snapshot_digest,
        "ordinal_start": page.ordinal_start,
        "records": [record.model_dump(mode="json") for record in page.records],
        "next_cursor": page.next_cursor,
    }
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def checkpoint_digest(
    snapshot_id: str, snapshot_digest: str, last_ordinal: int,
    cursor: str | None, page_ordinal_start: int | None = None,
    page_digest: str | None = None,
) -> str:
    value = {
        "snapshot_id": snapshot_id,
        "snapshot_digest": snapshot_digest,
        "last_ordinal": last_ordinal,
        "cursor": cursor,
    }
    if page_ordinal_start is not None or page_digest is not None:
        value.update({"page_ordinal_start": page_ordinal_start, "page_digest": page_digest})
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


__all__ = [
    "DurableSourcePage", "GraphRelationshipWrite", "GraphRebuildCheckpoint",
    "GraphRebuildRequest", "GraphRebuildResult", "GraphSourceRecord", "GraphTombstone",
    "GraphWriteResult", "checkpoint_digest", "immutable_digest", "relationship_id",
    "source_page_digest",
    "source_key", "tombstone_key",
    "VisibilityScope",
]
