"""Strict, immutable provenance contracts owned by Telemetry."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, JsonValue, StringConstraints,
    field_validator,
)

from factory.mcp_utils.interface import is_bounded_json

from .trace_context import TraceContextModel, validate_tracestate


def _validate_bounded(value: object) -> object:
    if not is_bounded_json(value):
        raise ValueError("provenance JSON exceeds bounded evidence limits")
    return value

MAX_INGEST_ITEMS = 256
MAX_READ_FIELDS = 64
MAX_MATERIALIZE_REFS = 256
MAX_MAPPING_REFS = 64

SignalType = Literal["span", "log", "metric"]
VisibilityScope = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class ProvenanceModel(BaseModel):
    """Strict transport model base for provenance data."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AuthenticatedTelemetryContext(ProvenanceModel):
    """Server-bound identity; never accepted as an ingest request field."""

    tenant_id: str = Field(min_length=1, max_length=128)
    producer_id: str = Field(min_length=1, max_length=128)
    principal_id: str = Field(min_length=1, max_length=256)
    visibility: VisibilityScope
    source_namespace: str = Field(min_length=1, max_length=256)


class TelemetryIngestItem(ProvenanceModel):
    source_id: str = Field(min_length=1, max_length=256)
    canonical_payload: JsonValue
    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{32}$")
    span_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{16}$")
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{16}$")
    trace_flags: int | None = Field(default=None, ge=0, le=255)
    tracestate: str | None = None
    trace_context: TraceContextModel | None = None
    signal: SignalType
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    _payload_bounded = field_validator("canonical_payload", mode="after")(_validate_bounded)
    _attributes_bounded = field_validator("attributes", mode="after")(_validate_bounded)

    @field_validator("trace_id", "span_id", "parent_span_id")
    @classmethod
    def reject_zero_w3c_ids(cls, value: str | None) -> str | None:
        """Reject the W3C invalid all-zero trace and span identifiers."""
        if value is not None and not int(value, 16):
            raise ValueError("W3C identifiers must not be all zero")
        return value

    @field_validator("tracestate")
    @classmethod
    def validate_w3c_tracestate(cls, value: str | None) -> str | None:
        return validate_tracestate(value) if value is not None else None


class TelemetryIngestBatch(ProvenanceModel):
    batch_id: str = Field(min_length=1, max_length=256)
    items: list[TelemetryIngestItem] = Field(max_length=MAX_INGEST_ITEMS)


class TelemetryIdempotencyRecord(ProvenanceModel):
    tenant_id: str
    producer_id: str
    key_kind: Literal["batch", "source"]
    key: str
    fingerprint: str
    outcome_ref: str
    persisted_at: datetime
    policy_version: str = "unknown"
    policy_outcome: str = "retained"
    policy_evidence: dict[str, JsonValue] = Field(default_factory=dict)


class TelemetryItemOutcome(ProvenanceModel):
    source_id: str
    status: Literal[
        "accepted", "duplicate", "conflict", "rejected", "sampled_out",
        "retained_unmaterialized", "materialized",
    ]
    telemetry_ref: str | None = None
    retryable: bool
    reason: str | None = None
    policy_version: str | None = None
    policy_outcome: str | None = None


class TelemetryIngestResult(ProvenanceModel):
    batch_id: str
    status: Literal["accepted", "duplicate", "partial_failure", "conflict", "rejected"]
    outcomes: list[TelemetryItemOutcome]
    retryable_source_ids: list[str]


class TelemetryReferenceRead(ProvenanceModel):
    telemetry_id: str = Field(min_length=1, max_length=512)
    requested_fields: set[str] = Field(max_length=MAX_READ_FIELDS)

    @field_validator("requested_fields", mode="before")
    @classmethod
    def normalize_wire_fields(cls, value: object) -> object:
        """Accept JSON arrays while retaining strict string members."""
        return set(value) if isinstance(value, list) else value


class AuthorizationDecision(ProvenanceModel):
    permitted: bool
    permitted_fields: set[str]
    denial_code: str | None = None


class TelemetryReferenceResult(ProvenanceModel):
    telemetry_id: str
    found: bool
    authorized: bool
    fields: dict[str, JsonValue] | None = None
    decision: AuthorizationDecision


class TelemetryStoredRecord(ProvenanceModel):
    telemetry_ref: str
    context: AuthenticatedTelemetryContext
    item: TelemetryIngestItem
    retained_at: datetime
    policy_version: str = "unknown"
    policy_outcome: Literal["retained", "redacted", "sampled_out"] = "retained"
    policy_evidence: dict[str, JsonValue] = Field(default_factory=dict)
    materialized: bool = False


from .provenance_mapping_models import (
    MappingActivationRecord, MappingEdge, MappingNodeRef, MaterializationMapping,
    MaterializationTarget,
)


class TelemetryMaterialize(ProvenanceModel):
    telemetry_ids: list[str] = Field(max_length=MAX_MATERIALIZE_REFS)
    mappings: list[tuple[str, str]] = Field(max_length=MAX_MAPPING_REFS)

    @field_validator("mappings", mode="before")
    @classmethod
    def normalize_wire_pairs(cls, value: object) -> object:
        """Accept JSON arrays while retaining strict tuple element types."""
        if not isinstance(value, list):
            return value
        return [tuple(item) if isinstance(item, list) else item for item in value]


class TelemetryMaterializeResult(ProvenanceModel):
    outcomes: list[TelemetryItemOutcome]
    materialized: int
    retained_unmaterialized: int
    retryable_telemetry_ids: list[str]


__all__ = [
    "AuthenticatedTelemetryContext", "AuthorizationDecision", "MappingEdge",
    "MappingNodeRef", "MaterializationMapping", "MaterializationTarget", "MappingActivationRecord",
    "TelemetryIngestBatch", "TelemetryIngestItem", "TelemetryIngestResult",
    "TelemetryIdempotencyRecord", "TelemetryItemOutcome", "TelemetryMaterialize",
    "TelemetryMaterializeResult", "TelemetryReferenceRead", "TelemetryReferenceResult",
    "TelemetryStoredRecord",
    "MAX_INGEST_ITEMS", "MAX_READ_FIELDS", "MAX_MATERIALIZE_REFS", "MAX_MAPPING_REFS",
    "SignalType", "VisibilityScope",
]
