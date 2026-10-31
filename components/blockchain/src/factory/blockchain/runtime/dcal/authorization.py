"""Internal narrow authorization seam for a future DCAL append runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from factory.blockchain.mcp.contracts.dcal.models import ProducerOperation

from .trusted import TrustedEnvelope, resolve_trusted_envelope


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Bounded authorization outcome; denial never permits downstream work."""

    allowed: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool) or not self.reason or len(self.reason) > 128:
            raise ValueError("invalid authorization decision")


class DcalAuthorizationPort(Protocol):
    """Future runtime policy seam, invoked only after a verified request permit."""

    def authorize_append(
        self, *, envelope: TrustedEnvelope, operation: ProducerOperation,
    ) -> AuthorizationDecision:
        """Authorize append for the exact verified binding and operation."""
        ...


def _authorize_append(
    *, permit: object | None, policy: DcalAuthorizationPort, operation: ProducerOperation,
) -> AuthorizationDecision:
    """Narrow internal gate; no caller callback or arbitrary action injection."""
    envelope = resolve_trusted_envelope(permit)
    if envelope is None:
        return AuthorizationDecision(False, "untrusted_context")
    if type(operation) is not ProducerOperation:
        return AuthorizationDecision(False, "invalid_operation")
    if not _matches(envelope, operation):
        return AuthorizationDecision(False, "operation_binding_mismatch")
    decision = policy.authorize_append(envelope=envelope, operation=operation)
    return decision if type(decision) is AuthorizationDecision else AuthorizationDecision(False, "invalid_authorization_decision")


def _matches(envelope: TrustedEnvelope, operation: ProducerOperation) -> bool:
    binding = envelope.binding
    return (
        operation.claimed_tenant_id == binding.tenant_id
        and operation.claimed_principal_id == binding.principal_id
        and operation.claimed_producer_id == binding.producer_id
        and operation.claimed_ledger_id == binding.ledger_id
        and operation.policy_digest == binding.policy_digest
    )


__all__ = ["AuthorizationDecision", "DcalAuthorizationPort"]
