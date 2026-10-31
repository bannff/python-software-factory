"""Strict contracts for trusted Graph projection events."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import DTO, JsonObject
from .operational import PublishOutput


class ProjectionReference(DTO):
    kind: str = Field(min_length=1, max_length=32)
    local_id: str = Field(min_length=1, max_length=128)
    entity_type: str = Field(min_length=1, max_length=64)
    relation_type: str = Field(min_length=1, max_length=64)


class ProjectionRecord(DTO):
    source_system: str = Field(min_length=1, max_length=64)
    action: Literal["upsert", "tombstone"]
    subject_kind: str = Field(min_length=1, max_length=32)
    subject_local_id: str = Field(min_length=1, max_length=128)
    subject_type: str = Field(min_length=1, max_length=64)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    references: list[ProjectionReference] = Field(default_factory=list, max_length=32)


class TrustedProjectionInput(DTO):
    tenant_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["graph.projection.requested"]
    subject_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0)
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    record: ProjectionRecord


class TrustedLearningSignalInput(DTO):
    """One trusted, tenant-bound downstream learning-signal publication.

    ``payload`` is the already-validated canonical learning payload; the
    Events-internal producer digests it and the digest is re-verified here so
    a public or spoofed caller cannot forge a protected downstream event.
    """

    tenant_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["reward.computed", "memory.learning_stored"]
    subject_id: str = Field(min_length=1, max_length=256)
    revision: int = Field(ge=0)
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: JsonObject


class TrustedDevLoopInput(DTO):
    tenant_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["dev_loop.cycle.completed"]
    subject_id: str = Field(min_length=1, max_length=256)
    revision: int = Field(ge=1)
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    loop_id: str = Field(min_length=1, max_length=128)
    cycle_id: str = Field(min_length=1, max_length=256)
    workflow_run_id: str = Field(min_length=1, max_length=256)
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_summary: str = Field(min_length=1, max_length=16_384)
    output_summary: str = Field(min_length=1, max_length=32_768)


class DevLoopScoreOutput(DTO):
    scored: bool
    reward: JsonObject | None = None
    error: str | None = None


__all__ = [
    "DevLoopScoreOutput", "ProjectionRecord", "ProjectionReference",
    "PublishOutput", "TrustedDevLoopInput", "TrustedLearningSignalInput",
    "TrustedProjectionInput",
]

