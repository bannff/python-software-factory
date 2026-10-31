"""Adversarial tests proving DCAL remains fail-closed before gateway integration."""
from __future__ import annotations

import asyncio

import pytest

from factory.blockchain.mcp.contracts.dcal import (
    ProducerOperation, ProducerSignature, ProtectedEvidenceRef, SubjectRef, TrustedBinding,
)
from factory.blockchain.runtime.dcal import __all__ as dcal_exports
from factory.blockchain.runtime.dcal.authorization import AuthorizationDecision, _authorize_append
from factory.blockchain.runtime.dcal.trusted import TrustedEnvelope, resolve_trusted_envelope
from factory.mcp_utils.interface import reset_envelope, set_envelope

from ._dcal_test_fixture import (
    authenticated_dcal_context,
    trusted_permit,
    unauthenticated_dcal_context,
)

_DIGEST = "a" * 64
_SIGNATURE = "A" * 86


def _binding() -> TrustedBinding:
    return TrustedBinding(tenant_id="tenant-1", ledger_id="ledger-1", principal_id="principal-1",
                          producer_id="producer-1", policy_digest=_DIGEST)


def _operation() -> ProducerOperation:
    return ProducerOperation(operation_id="operation-1", operation_kind="artifact_recorded",
        claimed_tenant_id="tenant-1", claimed_principal_id="principal-1", claimed_producer_id="producer-1",
        source_id="source-1", claimed_ledger_id="ledger-1", policy_id="policy-1", policy_digest=_DIGEST,
        subjects=(SubjectRef(subject_id="subject:1"),), evidence_refs=(ProtectedEvidenceRef(evidence_id="evidence:1", digest=_DIGEST),),
        idempotency_key="request-1", signature=ProducerSignature(key_id="key-1", signature_b64url=_SIGNATURE))


class _AllowAllPolicy:
    def __init__(self) -> None: self.calls = 0
    def authorize_append(self, **_: object) -> AuthorizationDecision:
        self.calls += 1
        return AuthorizationDecision(True, "allowed")


def test_public_runtime_offers_no_mint_scope_or_generic_callback_gate() -> None:
    assert {"mint_trusted_envelope", "set_trusted_envelope", "reset_trusted_envelope", "authorize_then"}.isdisjoint(dcal_exports)
    with pytest.raises(TypeError):
        TrustedEnvelope(_binding())  # type: ignore[call-arg]


def test_caller_bindings_generic_envelopes_and_test_permits_fail_closed() -> None:
    forged = {"tenant_id": "tenant-1", "principal_id": "principal-1"}
    token = set_envelope(forged)
    try:
        assert resolve_trusted_envelope() is None
    finally:
        reset_envelope(token)
    policy = _AllowAllPolicy()
    result = _authorize_append(permit=trusted_permit(_binding()), policy=policy, operation=_operation())
    assert result == AuthorizationDecision(False, "untrusted_context")
    assert policy.calls == 0


def test_authenticated_fixture_allows_matching_operation_only_within_scope(monkeypatch) -> None:
    policy = _AllowAllPolicy()
    with authenticated_dcal_context(monkeypatch, _binding()) as permit:
        result = _authorize_append(permit=permit, policy=policy, operation=_operation())
        assert result == AuthorizationDecision(True, "allowed")
        assert policy.calls == 1
    assert _authorize_append(permit=permit, policy=policy, operation=_operation()) == AuthorizationDecision(False, "untrusted_context")
    assert policy.calls == 1


def test_authenticated_fixture_rejects_separately_minted_permit_before_policy(monkeypatch) -> None:
    policy = _AllowAllPolicy()
    with authenticated_dcal_context(monkeypatch, _binding()):
        result = _authorize_append(permit=trusted_permit(_binding()), policy=policy, operation=_operation())
    assert result == AuthorizationDecision(False, "untrusted_context")
    assert policy.calls == 0


def test_unauthenticated_fixture_rejects_valid_looking_test_permit_before_policy(monkeypatch) -> None:
    policy = _AllowAllPolicy()
    with unauthenticated_dcal_context(monkeypatch):
        result = _authorize_append(permit=trusted_permit(_binding()), policy=policy, operation=_operation())
    assert result == AuthorizationDecision(False, "untrusted_context")
    assert policy.calls == 0


def test_authenticated_fixture_rejects_mismatched_principal_before_policy(monkeypatch) -> None:
    policy = _AllowAllPolicy()
    operation = _operation().model_copy(update={"claimed_principal_id": "principal-2"})
    with authenticated_dcal_context(monkeypatch, _binding()) as permit:
        result = _authorize_append(permit=permit, policy=policy, operation=operation)
    assert result == AuthorizationDecision(False, "operation_binding_mismatch")
    assert policy.calls == 0


def test_authenticated_fixture_rejects_invalid_operation_before_policy(monkeypatch) -> None:
    policy = _AllowAllPolicy()
    with authenticated_dcal_context(monkeypatch, _binding()) as permit:
        result = _authorize_append(permit=permit, policy=policy, operation=object())  # type: ignore[arg-type]
    assert result == AuthorizationDecision(False, "invalid_operation")
    assert policy.calls == 0


def test_child_task_cannot_inherit_authority_after_parent_reset() -> None:
    async def run() -> object:
        ready = asyncio.Event()
        release = asyncio.Event()
        async def child() -> object:
            ready.set()
            await release.wait()
            return resolve_trusted_envelope()
        parent = set_envelope({"tenant_id": "tenant-1"})
        try:
            child_task = asyncio.create_task(child())
            await ready.wait()
        finally:
            reset_envelope(parent)
        release.set()
        return await child_task
    assert asyncio.run(run()) is None
