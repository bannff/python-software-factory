"""Caller-bound native invocation with exact service-only permits."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .pools import _run_sync_agent
from .tool_dispatch import transport_failure


class NativeEnvelopeInvoker:
    """Invoke structured targets; protected calls require one strict binding."""

    def __init__(self, aggregator: Any, *, caller: str | None = None):
        self._aggregator = aggregator
        self._caller = caller

    def for_caller(self, caller: str) -> "NativeEnvelopeInvoker":
        """Create an immutable caller-bound capability for trusted composition."""
        if not isinstance(caller, str) or not caller.strip():
            raise ValueError("caller must be a non-empty string")
        return NativeEnvelopeInvoker(self._aggregator, caller=caller.strip())

    bind = for_caller

    def __call__(
        self, target: Mapping[str, str], *, arguments: dict[str, Any],
        idempotency_key: str, envelope: dict[str, Any],
        enrollment: Mapping[str, Any] | None = None,
        attempt: Mapping[str, Any] | None = None,
        protected_artifact: Mapping[str, Any] | None = None,
        credential_slot: Mapping[str, Any] | None = None,
        credential_egress: Mapping[str, Any] | None = None,
        steer: Mapping[str, Any] | None = None,
        completion: Mapping[str, Any] | None = None,
        lesson_proposal: Mapping[str, Any] | None = None,
        projection: Mapping[str, Any] | None = None,
        migration_import: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        brick_name = target.get("brick_name")
        tool_name = target.get("tool_name")
        if not brick_name or not tool_name:
            return transport_failure("ToolNotFoundError", "Invalid structured tool target")
        brick_mcp, resolved, error = self._aggregator.resolve_brick_tool(
            brick_name, tool_name,
        )
        if error or brick_mcp is None or resolved is None:
            return transport_failure("ToolNotFoundError", error or "Unknown tool")
        tool = _run_sync_agent(brick_mcp.get_tool(resolved))
        if tool is None:
            return transport_failure("ToolNotFoundError", "Unknown tool")
        merged, error = self._merged_envelope(envelope, idempotency_key)
        if error is not None:
            return error
        claims, error = self._claims_for(
            tool, brick_name, resolved, merged, {
                "enrollment": enrollment, "attempt": attempt,
                "protected_artifact": protected_artifact,
                "credential_slot": credential_slot,
                "credential_egress": credential_egress, "steer": steer,
                "completion": completion, "lesson_proposal": lesson_proposal,
                "projection": projection, "migration_import": migration_import,
            },
        )
        if error is not None:
            return error
        return self._invoke(
            brick_name, tool_name, tool, arguments, merged, claims,
        )

    @staticmethod
    def _merged_envelope(
        envelope: dict[str, Any], idempotency_key: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        from factory.mcp_utils.interface import (
            get_envelope, normalize_correlation, normalize_envelope,
        )
        try:
            ambient = normalize_envelope(get_envelope())
            explicit = normalize_envelope(dict(envelope))
            normalize_correlation(ambient, explicit)
            trusted_correlation = normalize_correlation(ambient)
        except (TypeError, ValueError) as exc:
            return {}, transport_failure("EnvelopeConflictError", str(exc))
        attributes = dict(explicit.get("attributes") or {})
        attributes.update(dict(ambient.get("attributes") or {}))
        merged = {**explicit, **ambient, "attributes": attributes}
        merged.update(trusted_correlation)
        if trusted_correlation.get("correlation_id"):
            merged["request_id"] = trusted_correlation["correlation_id"]
        # Stamp only a real key: a None here reaches Envelope's strict
        # str|int|float|bool union downstream and fails every call (#89 follow-up).
        if idempotency_key is not None:
            merged["attributes"] = {
                **dict(merged.get("attributes") or {}),
                "workflow_attempt_id": idempotency_key,
            }
        return merged, None

    def _claims_for(
        self, tool: Any, audience: str, target_tool: str,
        envelope: dict[str, Any], sources: dict[str, Mapping[str, Any] | None],
    ) -> tuple[Any, dict[str, Any] | None]:
        from factory.mcp_utils.interface import (
            AttemptBinding, CredentialEgressBinding, CredentialSlotBinding,
            EnrollmentBinding, ExecutionBinding, ProtectedArtifactBinding,
            SteerBinding, CompletionBinding, LessonProposalBinding,
            ProjectionBinding, MigrationImportBinding,
            is_service_only, mint_internal_invocation_claims, service_binding,
        )
        supplied = sum(value is not None for value in sources.values())
        if not is_service_only(tool):
            if supplied:
                return None, self._access_error("public targets accept no internal binding")
            return None, None
        if self._caller is None:
            return None, self._access_error("caller-bound capability required")
        if supplied != 1:
            return None, self._access_error("exactly one complete operation binding is required")
        specs: dict[str, tuple[Any, set[str], str]] = {
            "enrollment": (EnrollmentBinding, {"run_key", "manifest_digest"}, "enrollment"),
            "attempt": (AttemptBinding, {"workflow_run_id", "attempt_id", "revision", "manifest_digest"}, "attempt"),
            "execution": (ExecutionBinding, {"workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest", "request_digest", "provider_request_digest"}, "attempt"),
            "protected_artifact": (ProtectedArtifactBinding, {"artifact_ref", "fingerprint"}, "protected_artifact"),
            "credential_slot": (CredentialSlotBinding, {"tenant_id", "owner_id", "provider_id", "connection_ref", "slot_kind", "generation"}, "credential_slot"),
            "credential_egress": (CredentialEgressBinding, {"provider_id", "route_id", "connection_ref", "request_digest"}, "credential_egress"),
            "steer": (SteerBinding, {"tenant_id", "owner_id", "session_id", "delivery_id", "revision"}, "steer"),
            "completion": (CompletionBinding, {"tenant_id", "owner_id", "session_id", "run_id", "revision", "result_digest"}, "completion"),
            "lesson_proposal": (LessonProposalBinding, {"tenant_id", "owner_id", "source_ref", "proposal_digest"}, "lesson_proposal"),
            "projection": (ProjectionBinding, {"tenant_id", "owner_id", "event_type", "subject_id", "revision", "payload_digest"}, "projection"),
            "migration_import": (MigrationImportBinding, {"tenant_id", "owner_id", "source_adapter", "source_fingerprint", "plan_digest", "kind", "source_record_id", "target_digest"}, "migration_import"),
        }
        spec = specs.get(service_binding(tool) or "")
        binding = None
        if spec is not None:
            cls, fields, source_name = spec
            # the single supplied binding must be exactly the expected kind's source
            if sources.get(source_name) is not None and all(
                key == source_name or value is None for key, value in sources.items()
            ):
                binding = self._parse_binding(cls, sources[source_name], fields)
        if binding is None:
            return None, self._access_error("operation binding is partial, mixed, or wrong")
        if service_binding(tool) in {"attempt", "execution"} and envelope.get("run_id") != binding.workflow_run_id:
            return None, self._access_error("trusted workflow run does not match operation binding")
        try:
            claims = mint_internal_invocation_claims(
                caller=self._caller, audience=audience, target_tool=target_tool,
                binding=binding, target=tool,
            )
        except (TypeError, ValueError) as exc:
            return None, self._access_error(str(exc))
        return claims, None

    @staticmethod
    def _parse_binding(cls: Any, value: Any, fields: set[str]) -> Any | None:
        if not isinstance(value, Mapping) or set(value) != fields:
            return None
        try:
            return cls(**dict(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _access_error(message: str) -> dict[str, Any]:
        return transport_failure("ServiceOnlyAccessError", message)

    def _invoke(
        self, brick_name: str, tool_name: str, tool: Any,
        arguments: dict[str, Any], envelope: dict[str, Any], claims: Any,
    ) -> dict[str, Any]:
        from factory.mcp_utils.interface import (
            project_envelope_arguments, reset_envelope,
            reset_internal_invocation_claims, set_envelope,
            set_internal_invocation_claims,
        )
        projected = project_envelope_arguments(tool.fn, arguments, envelope)
        envelope_token = set_envelope(envelope)
        claims_token = set_internal_invocation_claims(claims) if claims else None
        try:
            return _run_sync_agent(
                self._aggregator.call_brick_tool(
                    brick_name, tool_name, projected,
                ),
            )
        finally:
            reset_internal_invocation_claims(claims_token)
            reset_envelope(envelope_token)
