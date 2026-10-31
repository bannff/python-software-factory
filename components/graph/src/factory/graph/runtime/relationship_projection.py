"""Graph-owned deterministic relationship projection semantics."""
from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import protected_canonical_json

from .neighborhood import encode_node_id
from .ports import Entity, Relationship

_KINDS = Literal["memory", "kb", "lesson", "session", "workflow-run", "entity"]
_RELATIONS = {"derived_from", "mentions", "learned_in", "about_run", "supersedes"}


class ProjectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ProjectionReference(ProjectionModel):
    kind: _KINDS
    local_id: str = Field(min_length=1, max_length=128)
    entity_type: str = Field(min_length=1, max_length=64)
    relation_type: str = Field(min_length=1, max_length=64)


class ProjectionRecord(ProjectionModel):
    source_system: str = Field(min_length=1, max_length=64)
    action: Literal["upsert", "tombstone"]
    subject_kind: _KINDS
    subject_local_id: str = Field(min_length=1, max_length=128)
    subject_type: str = Field(min_length=1, max_length=64)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    references: list[ProjectionReference] = Field(default_factory=list, max_length=32)


class ProjectionApplyResult(ProjectionModel):
    subject_node_id: str
    status: Literal["created", "updated", "matched", "conflict", "stale", "tombstoned"]
    entities_written: int = 0
    relationships_written: int = 0


def record_digest(record: ProjectionRecord | dict) -> str:
    parsed = ProjectionRecord.model_validate(record)
    return hashlib.sha256(protected_canonical_json(
        parsed.model_dump(mode="json"),
    )).hexdigest()


def apply_projection(
    graph, *, tenant_id: str, owner_id: str, subject_id: str,
    revision: int, payload_digest: str, record: ProjectionRecord | dict,
) -> ProjectionApplyResult:
    parsed = ProjectionRecord.model_validate(record)
    if parsed.subject_local_id != subject_id or record_digest(parsed) != payload_digest:
        raise ValueError("projection binding does not match record")
    if any(item.relation_type not in _RELATIONS for item in parsed.references):
        raise ValueError("unsupported projection relationship")
    subject = encode_node_id(
        parsed.subject_kind, tenant_id, owner_id, parsed.subject_local_id,
    )
    if parsed.action == "tombstone":
        graph.delete_entity(subject)
        return ProjectionApplyResult(subject_node_id=subject, status="tombstoned")
    existing = graph.get_entity(subject)
    status = _status(existing, revision, parsed.source_digest)
    if status in {"conflict", "stale", "matched"}:
        return ProjectionApplyResult(subject_node_id=subject, status=status)
    properties = {
        "tenant_id": tenant_id, "principal_id": owner_id,
        "source_system": parsed.source_system,
        "local_id": parsed.subject_local_id, "revision": revision,
        "source_digest": parsed.source_digest,
    }
    entity = Entity(subject, parsed.subject_type, properties)
    graph.add_entity(entity) if existing is None else graph.update_entity(entity)
    relationships = 0
    for reference in parsed.references:
        target = encode_node_id(reference.kind, tenant_id, owner_id, reference.local_id)
        if graph.get_entity(target) is None:
            graph.add_entity(Entity(target, reference.entity_type, {
                "tenant_id": tenant_id, "principal_id": owner_id,
                "local_id": reference.local_id,
            }))
        identity = hashlib.sha256(protected_canonical_json({
            "tenant_id": tenant_id, "principal_id": owner_id,
            "source": subject, "target": target,
            "type": reference.relation_type, "revision": revision,
        })).hexdigest()
        graph.add_relationship(Relationship(
            "projection-" + identity, reference.relation_type,
            subject, target, {"revision": revision, "source_digest": parsed.source_digest},
        ))
        relationships += 1
    return ProjectionApplyResult(
        subject_node_id=subject, status="created" if existing is None else "updated",
        entities_written=1, relationships_written=relationships,
    )


def _status(existing: Entity | None, revision: int, digest: str) -> str:
    if existing is None:
        return "created"
    current = existing.properties.get("revision")
    if isinstance(current, int) and current > revision:
        return "stale"
    if current == revision:
        return "matched" if existing.properties.get("source_digest") == digest else "conflict"
    return "updated"


__all__ = [
    "ProjectionApplyResult", "ProjectionRecord", "ProjectionReference",
    "apply_projection", "record_digest",
]
