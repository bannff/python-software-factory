"""Authenticated Telemetry provenance runtime facade."""
from __future__ import annotations

from factory.mcp_utils.interface import get_service

from .provenance_ingest import ingest
from .provenance_materialization import materialize
from .provenance_models import (
    AuthenticatedTelemetryContext,
    MappingActivationRecord,
    TelemetryIngestBatch,
    TelemetryIngestResult,
    TelemetryMaterialize,
    TelemetryMaterializeResult,
    TelemetryReferenceRead,
    TelemetryReferenceResult,
)
from .provenance_reference import read_reference
from .policy_config import compose_retention_policy
from .provenance_policy import RetentionPolicy
from .provenance_resolution import TargetResolver, validate_activation_targets
from .provenance_store import JsonProvenanceStore, ProvenanceStore
from .provenance_support import (
    ProvenanceAuthenticationError,
    authenticated_context,
    fingerprint,
    telemetry_ref,
)


class TelemetryProvenanceRuntime:
    """Coordinate the focused provenance capabilities and durable store."""

    def __init__(
        self,
        store: ProvenanceStore | None = None,
        policy: RetentionPolicy | None = None,
        target_resolver: TargetResolver | None = None,
    ) -> None:
        self.store = store or JsonProvenanceStore()
        self.policy = policy or compose_retention_policy()
        self._target_resolver = target_resolver
        load_activation = getattr(self.store, "get_activation", None)
        self._activation = load_activation() if load_activation else None

    def activate_mapping(self, record: MappingActivationRecord) -> MappingActivationRecord:
        parsed = MappingActivationRecord.model_validate(record)
        self._activation = validate_activation_targets(parsed, self._target_resolver)
        persist_activation = getattr(self.store, "put_activation", None)
        if persist_activation:
            persist_activation(self._activation)
        return self._activation

    def ingest(
        self,
        batch: TelemetryIngestBatch,
        context: AuthenticatedTelemetryContext | None = None,
    ) -> TelemetryIngestResult:
        ctx = context or authenticated_context()
        return ingest(self.store, batch, ctx, self.policy)

    def read_reference(
        self,
        request: TelemetryReferenceRead,
        context: AuthenticatedTelemetryContext | None = None,
    ) -> TelemetryReferenceResult:
        ctx = context or authenticated_context()
        return read_reference(self.store, request, ctx)

    def materialize(
        self,
        request: TelemetryMaterialize,
        context: AuthenticatedTelemetryContext | None = None,
    ) -> TelemetryMaterializeResult:
        ctx = context or authenticated_context()
        return materialize(
            self.store, self._activation, request, ctx, get_service,
        )


# Preserve the old module-level private helper names for same-brick callers.
_fingerprint = fingerprint
_ref = telemetry_ref


__all__ = [
    "ProvenanceAuthenticationError", "TelemetryProvenanceRuntime",
    "authenticated_context",
]
