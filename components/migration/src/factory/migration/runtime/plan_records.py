"""Immutable parser-approved records bound to one Migration plan."""
from __future__ import annotations

import json
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .receipt_models import CommitStatus, PlanIdentity
from .source_models import (
    SafeLesson, SafeMarkdown, SafeMemory, SafeSchedule, SourceKind, sha256_hex,
)

SafePayload = SafeMemory | SafeLesson | SafeSchedule | SafeMarkdown
_EXPECTED = {
    SourceKind.MEMORY: SafeMemory,
    SourceKind.LESSONS: SafeLesson,
    SourceKind.SCHEDULES: SafeSchedule,
    SourceKind.MARKDOWN: SafeMarkdown,
}


class PlanRecord(BaseModel):
    """One bounded source record frozen under an owner-scoped plan identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    adapter: str
    source_fingerprint: str
    plan_digest: str
    kind: SourceKind
    source_record_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: SafePayload

    @classmethod
    def from_source(
        cls, plan: PlanIdentity, kind: SourceKind, payload: SafePayload,
    ) -> "PlanRecord":
        return cls(
            tenant_id=plan.tenant_id, owner_id=plan.owner_id,
            adapter=plan.adapter, source_fingerprint=plan.source_fingerprint,
            plan_digest=plan.plan_digest, kind=kind,
            source_record_id=payload.identity, payload=payload,
        )

    @model_validator(mode="after")
    def _matching_payload(self) -> "PlanRecord":
        if not isinstance(self.payload, _EXPECTED[self.kind]):
            raise ValueError("plan record payload does not match kind")
        if self.payload.identity != self.source_record_id:
            raise ValueError("plan record identity mismatch")
        PlanIdentity(
            tenant_id=self.tenant_id, owner_id=self.owner_id,
            adapter=self.adapter, source_fingerprint=self.source_fingerprint,
            plan_digest=self.plan_digest, kinds=(self.kind.value,),
        )
        return self

    @property
    def payload_json(self) -> str:
        return json.dumps(
            self.payload.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False,
        )

    @property
    def payload_digest(self) -> str:
        return f"sha256:{sha256_hex(self.payload_json)}"


class PlanRecordCommit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: CommitStatus
    record: PlanRecord


def parse_payload(kind: SourceKind, payload_json: str) -> SafePayload:
    """Reconstruct the exact strict source model selected by the stored kind."""
    return _EXPECTED[kind].model_validate_json(payload_json)


__all__ = [
    "PlanRecord", "PlanRecordCommit", "SafePayload", "parse_payload",
]
