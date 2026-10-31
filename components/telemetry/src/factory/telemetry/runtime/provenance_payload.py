"""Generic, validated payload adapter for provenance materialization."""
from __future__ import annotations

import hashlib
import json

from pydantic import Field, JsonValue, field_validator

from factory.mcp_utils.interface import is_bounded_json

from .provenance_models import AuthenticatedTelemetryContext, ProvenanceModel, TelemetryStoredRecord


class GraphRelationshipPayload(ProvenanceModel):
    """Flat payload compatible with Graph's GraphRelationshipWrite contract."""

    source_system: str = Field(min_length=1, max_length=128)
    source_identity: str = Field(min_length=1, max_length=256)
    source_digest: str = Field(min_length=1, max_length=256)
    relation_type: str = Field(min_length=1, max_length=128)
    source_endpoint: str = Field(min_length=1, max_length=512)
    target_endpoint: str = Field(min_length=1, max_length=512)
    source_ref: str = Field(min_length=1, max_length=512)
    visibility: str = Field(min_length=1, max_length=64)
    browse_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @classmethod
    def from_record(
        cls, record: TelemetryStoredRecord, context: AuthenticatedTelemetryContext,
    ) -> "GraphRelationshipPayload":
        digest_input = {
            "context": context.model_dump(mode="json"),
            "item": record.item.model_dump(mode="json"),
            "telemetry_ref": record.telemetry_ref,
        }
        digest = hashlib.sha256(_canonical(digest_input)).hexdigest()
        identity = "telemetry-source-" + hashlib.sha256(
            _canonical([context.tenant_id, context.producer_id, record.item.source_id])
        ).hexdigest()
        metadata = {
            "telemetry_ref": record.telemetry_ref,
            "source_id": record.item.source_id,
            "signal": record.item.signal,
            "trace_id": record.item.trace_id,
            "span_id": record.item.span_id,
            "parent_span_id": record.item.parent_span_id,
            "tenant_id": context.tenant_id,
            "producer_id": context.producer_id,
            "source_namespace": context.source_namespace,
            "attributes": record.item.attributes,
        }
        run_id = _canonical_run_id(record.item.attributes)
        if run_id is not None:
            metadata["run_id"] = run_id
        return cls(
            source_system="telemetry",
            source_identity=identity,
            source_digest=digest,
            relation_type="OBSERVED",
            source_endpoint=record.telemetry_ref,
            target_endpoint=_endpoint(context.source_namespace, record.item.source_id),
            source_ref=record.telemetry_ref,
            visibility=context.visibility,
            browse_metadata=metadata,
        )

    @field_validator("browse_metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not is_bounded_json(value):
            raise ValueError("materialization metadata exceeds bounded JSON limits")
        return value


def _canonical_run_id(attributes: dict[str, JsonValue]) -> str | None:
    aliases = {
        key: value.strip()
        for key in ("run_id", "workflow_run_id", "managed_graph.run_id")
        if isinstance((value := attributes.get(key)), str) and value.strip()
    }
    managed = attributes.get("managed_graph")
    if isinstance(managed, dict):
        value = managed.get("run_id")
        if isinstance(value, str) and value.strip():
            aliases["managed_graph.run_id"] = value.strip()
    values = set(aliases.values())
    if len(values) > 1:
        names = ", ".join(sorted(aliases))
        raise ValueError(f"conflicting non-empty run aliases: {names}")
    return next(iter(values), None)


def _endpoint(namespace: str, source_id: str) -> str:
    value = f"source:{namespace}:{source_id}"
    if len(value) <= 512:
        return value
    return "source:" + hashlib.sha256(value.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


__all__ = ["GraphRelationshipPayload"]
