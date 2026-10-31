"""Frozen, bounded dcal/v1 DTO foundations with no raw container fields."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_PROTOCOL = "dcal"
_VERSION = "v1"
_PROFILE = "dcal"
_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
_DIGEST = r"^[0-9a-f]{64}$"
_REF = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$"
# Signed 64-bit sequence values remain portable across ordered ledger/storage adapters.
_MAX_SEQUENCE = 2**63 - 1


class DcalDTO(BaseModel):
    """Strict immutable base for all dcal/v1 contract values."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DcalScope(DcalDTO):
    """Server-bound DCAL scope, never a public profile selector."""

    tenant_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    ledger_id: str = Field(min_length=1, max_length=128, pattern=_ID)


class TrustedBinding(DcalScope):
    """Gateway-verified binding required before DCAL work is authorized."""

    protocol: Literal["dcal"] = _PROTOCOL
    version: Literal["v1"] = _VERSION
    profile: Literal["dcal"] = _PROFILE
    principal_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    producer_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    policy_digest: str = Field(pattern=_DIGEST)


class DurableIdentity(TrustedBinding):
    """Idempotency namespace including every required DCAL identity dimension."""

    action: str = Field(min_length=1, max_length=64, pattern=_ID)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=_ID)


class ProducerSignature(DcalDTO):
    """Canonical producer signature; cryptographic verification is deferred."""

    key_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    algorithm: Literal["ecdsa-p256-sha256"] = "ecdsa-p256-sha256"
    signature_b64url: str = Field(
        min_length=86, max_length=86, pattern=r"^[A-Za-z0-9_-]{86}$",
    )


class SubjectRef(DcalDTO):
    """Opaque subject reference allowed in a redacted DCAL operation."""

    subject_id: str = Field(min_length=1, max_length=256, pattern=_REF)


class ProtectedEvidenceRef(DcalDTO):
    """Opaque reference to protected evidence; never carries inline evidence."""

    evidence_id: str = Field(min_length=1, max_length=256, pattern=_REF)
    digest: str = Field(pattern=_DIGEST)


class ProducerOperation(DcalDTO):
    """Bound, signed producer request with only canonical DCAL value objects."""

    @field_validator("subjects", "evidence_refs", "signature", mode="before")
    @classmethod
    def _reject_raw_nested_values(cls, value: object) -> object:
        if isinstance(value, dict) or (
            isinstance(value, (tuple, list)) and any(isinstance(item, dict) for item in value)
        ):
            raise ValueError("nested DCAL values must be DTO instances")
        return value

    operation_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    operation_kind: str = Field(min_length=1, max_length=64, pattern=_ID)
    claimed_tenant_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    claimed_principal_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    claimed_producer_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    source_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    claimed_ledger_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    policy_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    policy_digest: str = Field(pattern=_DIGEST)
    subjects: tuple[SubjectRef, ...] = Field(min_length=1, max_length=256)
    evidence_refs: tuple[ProtectedEvidenceRef, ...] = Field(max_length=256)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=_ID)
    signature: ProducerSignature


class DcalLogRecord(DcalDTO):
    """Minimal immutable append record shape for future isolated adapters."""

    record_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    sequence: int = Field(ge=0, le=_MAX_SEQUENCE)
    commitment: str = Field(pattern=_DIGEST)


class AppendDecision(DcalDTO):
    """Append-or-match result without exposing storage implementation details."""

    status: Literal["appended", "matched", "conflict"]
    record_id: str = Field(min_length=1, max_length=128, pattern=_ID)


class SourceSnapshot(DcalDTO):
    """Immutable source snapshot reference for deterministic projection paging."""

    snapshot_id: str = Field(min_length=1, max_length=128, pattern=_ID)
    snapshot_digest: str = Field(pattern=_DIGEST)


class AnchorDecision(DcalDTO):
    """Bounded evidence-only outcome for a future finalized-checkpoint anchor."""

    status: Literal["anchored", "failed"]
    evidence_id: str | None = Field(default=None, max_length=128, pattern=_ID)


class RecordPage(DcalDTO):
    """Bounded page result; records remain typed immutable values."""

    @field_validator("records", mode="before")
    @classmethod
    def _reject_raw_records(cls, value: object) -> object:
        if isinstance(value, (tuple, list)) and any(isinstance(item, dict) for item in value):
            raise ValueError("records must be DcalLogRecord instances")
        return value

    records: tuple[DcalLogRecord, ...] = Field(max_length=500)
    next_cursor: str | None = Field(default=None, max_length=256, pattern=_REF)


__all__ = [
    "AnchorDecision", "AppendDecision", "DcalDTO", "DcalLogRecord", "DcalScope", "DurableIdentity",
    "ProducerOperation", "ProducerSignature", "ProtectedEvidenceRef", "RecordPage",
    "SourceSnapshot", "SubjectRef", "TrustedBinding",
]
