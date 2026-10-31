"""Strict operation bindings for protected service handoffs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from .projection_binding import ProjectionBinding
from .migration_binding import MigrationImportBinding
BindingKind = Literal[
    "enrollment", "attempt", "execution", "protected_artifact",
    "credential_slot", "credential_egress", "steer", "completion",
    "lesson_proposal", "projection", "migration_import",
]
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SLOT_KINDS = frozenset({"client_secret", "refresh_token"})


def _text(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip(): raise ValueError(f"{name} must be a non-empty string")


def _digest(value: Any) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None: raise ValueError("digest must be a lowercase SHA-256 digest")


def _generation(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1: raise ValueError("generation must be a positive integer")


@dataclass(frozen=True, slots=True)
class EnrollmentBinding:
    run_key: str
    manifest_digest: str
    def __post_init__(self) -> None: _text("run_key", self.run_key); _digest(self.manifest_digest)


@dataclass(frozen=True, slots=True)
class AttemptBinding:
    workflow_run_id: str
    attempt_id: str
    revision: int
    manifest_digest: str
    def __post_init__(self) -> None:
        _text("workflow_run_id", self.workflow_run_id); _text("attempt_id", self.attempt_id)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0: raise ValueError("revision must be a non-negative integer")
        _digest(self.manifest_digest)


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    workflow_run_id: str
    attempt_id: str
    revision: int
    engine_id: str
    registration_digest: str
    request_digest: str
    provider_request_digest: str
    def __post_init__(self) -> None:
        _text("workflow_run_id", self.workflow_run_id); _text("attempt_id", self.attempt_id); _text("engine_id", self.engine_id)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1: raise ValueError("revision must be a positive integer")
        for value in (self.registration_digest, self.request_digest, self.provider_request_digest): _digest(value)


@dataclass(frozen=True, slots=True)
class ProtectedArtifactBinding:
    artifact_ref: str
    fingerprint: str
    def __post_init__(self) -> None:
        _text("artifact_ref", self.artifact_ref)
        _digest(self.fingerprint)


@dataclass(frozen=True, slots=True)
class CredentialSlotBinding:
    """One exact encrypted credential-slot operation, generation-fenced."""
    tenant_id: str
    owner_id: str
    provider_id: str
    connection_ref: str
    slot_kind: str
    generation: int
    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "provider_id", "connection_ref"):
            _text(name, getattr(self, name))
        if self.slot_kind not in _SLOT_KINDS: raise ValueError("slot_kind is not a known credential slot kind")
        _generation(self.generation)


@dataclass(frozen=True, slots=True)
class CredentialEgressBinding:
    """One exact tokenless credential-injecting egress operation."""
    provider_id: str
    route_id: str
    connection_ref: str
    request_digest: str
    def __post_init__(self) -> None:
        for name in ("provider_id", "route_id", "connection_ref"):
            _text(name, getattr(self, name))
        _digest(self.request_digest)


@dataclass(frozen=True, slots=True)
class SteerBinding:
    """One exact Agent acknowledgement of a steer delivery revision."""
    tenant_id: str
    owner_id: str
    session_id: str
    delivery_id: str
    revision: int
    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "delivery_id"):
            _text(name, getattr(self, name))
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) \
                or self.revision < 1:
            raise ValueError("revision must be a positive integer")


@dataclass(frozen=True, slots=True)
class CompletionBinding:
    """One exact background completion write or acknowledgement."""
    tenant_id: str
    owner_id: str
    session_id: str
    run_id: str
    revision: int
    result_digest: str
    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "run_id"):
            _text(name, getattr(self, name))
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) \
                or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        _digest(self.result_digest)



@dataclass(frozen=True, slots=True)
class LessonProposalBinding:
    """One exact automated lesson candidate from a trusted producer."""
    tenant_id: str
    owner_id: str
    source_ref: str
    proposal_digest: str
    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "source_ref"):
            _text(name, getattr(self, name))
        _digest(self.proposal_digest)

InvocationBinding = (
    EnrollmentBinding | AttemptBinding | ExecutionBinding | ProtectedArtifactBinding
    | CredentialSlotBinding | CredentialEgressBinding | SteerBinding
    | CompletionBinding | LessonProposalBinding | ProjectionBinding
    | MigrationImportBinding
)


def binding_kind(binding: InvocationBinding) -> BindingKind:
    if isinstance(binding, EnrollmentBinding): return "enrollment"
    if isinstance(binding, ProtectedArtifactBinding): return "protected_artifact"
    if isinstance(binding, CredentialSlotBinding): return "credential_slot"
    if isinstance(binding, CredentialEgressBinding): return "credential_egress"
    if isinstance(binding, SteerBinding): return "steer"
    if isinstance(binding, CompletionBinding): return "completion"
    if isinstance(binding, LessonProposalBinding): return "lesson_proposal"
    if isinstance(binding, ProjectionBinding): return "projection"
    if isinstance(binding, MigrationImportBinding): return "migration_import"
    return "execution" if isinstance(binding, ExecutionBinding) else "attempt"


def _nested_matches(binding: InvocationBinding, arguments: dict[str, Any], key: str) -> bool:
    nested = arguments.get(key)
    return isinstance(nested, dict) and set(binding.__dataclass_fields__) <= set(nested) \
        and all(nested.get(field) == getattr(binding, field) for field in binding.__dataclass_fields__)


def binding_matches(binding: InvocationBinding, arguments: dict[str, Any]) -> bool:
    if isinstance(binding, ProtectedArtifactBinding):
        artifact = arguments.get("artifact")
        return isinstance(artifact, dict) and set(binding.__dataclass_fields__) <= set(artifact) \
            and artifact.get("artifact_ref") == binding.artifact_ref \
            and artifact.get("fingerprint") == binding.fingerprint
    if isinstance(binding, CredentialSlotBinding):
        return _nested_matches(binding, arguments, "slot")
    if isinstance(binding, CredentialEgressBinding):
        return _nested_matches(binding, arguments, "request")
    if isinstance(binding, (SteerBinding, CompletionBinding, LessonProposalBinding,
                            ProjectionBinding, MigrationImportBinding)):
        return all(arguments.get(field) == getattr(binding, field)
                   for field in binding.__dataclass_fields__)
    fields = ("run_key", "manifest_digest") if isinstance(binding, EnrollmentBinding) else (
        "workflow_run_id", "attempt_id", "revision", "manifest_digest") if isinstance(binding, AttemptBinding) else (
        "workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest", "request_digest", "provider_request_digest")
    return all(arguments.get(field) == getattr(binding, field) for field in fields)


__all__ = ["AttemptBinding", "BindingKind", "EnrollmentBinding", "ExecutionBinding", "ProtectedArtifactBinding", "CredentialSlotBinding", "CredentialEgressBinding", "SteerBinding", "CompletionBinding", "LessonProposalBinding", "ProjectionBinding", "MigrationImportBinding", "InvocationBinding", "binding_kind", "binding_matches"]
