"""Focused strict-boundary tests for the isolated first DCAL contract slice."""
from __future__ import annotations

from collections.abc import Callable
from inspect import signature

from typing import get_type_hints

import pytest
from pydantic import BaseModel, ValidationError

from factory.blockchain.mcp.contracts.dcal import (
    AnchorDecision, AppendDecision, ConfigProperty, DcalCapabilities, DcalConfigSchema, DcalDTO,
    DcalHealth, DcalLogRecord, DcalScope, DurableIdentity, ProducerOperation,
    ProducerSignature, ProtectedEvidenceRef, RecordPage, SourceSnapshot, SubjectRef,
    TrustedBinding,
)
from factory.blockchain.runtime.dcal.ports import DcalAnchorPort, DcalLedgerPort, ProvenanceLedgerPort
from factory.blockchain.runtime.ports import LedgerPort

_DIGEST = "a" * 64
_SIGNATURE = "A" * 86
_MAX_SEQUENCE = 2**63 - 1


def _binding(**changes: object) -> TrustedBinding:
    values = {
        "tenant_id": "tenant-1", "ledger_id": "ledger-1", "principal_id": "principal-1",
        "producer_id": "producer-1", "policy_digest": _DIGEST,
    }
    values.update(changes)
    return TrustedBinding(**values)


def _operation(**changes: object) -> ProducerOperation:
    values = {
        "operation_id": "operation-1", "operation_kind": "artifact_recorded",
        "claimed_tenant_id": "tenant-1", "claimed_principal_id": "principal-1",
        "claimed_producer_id": "producer-1", "source_id": "source-1",
        "claimed_ledger_id": "ledger-1", "policy_id": "policy-1",
        "policy_digest": _DIGEST, "subjects": (SubjectRef(subject_id="subject:1"),),
        "evidence_refs": (ProtectedEvidenceRef(evidence_id="evidence:1", digest=_DIGEST),),
        "idempotency_key": "request-1",
        "signature": ProducerSignature(key_id="key-1", signature_b64url=_SIGNATURE),
    }
    values.update(changes)
    return ProducerOperation(**values)


def _property(**changes: object) -> ConfigProperty:
    values = {"name": "ledger_id", "value_type": "string", "required": True}
    values.update(changes)
    return ConfigProperty(**values)


_FACTORIES: tuple[tuple[type[BaseModel], Callable[[], BaseModel]], ...] = (
    (DcalCapabilities, DcalCapabilities), (DcalHealth, lambda: DcalHealth(healthy=True, status="ready")),
    (ConfigProperty, _property), (DcalConfigSchema, lambda: DcalConfigSchema(properties=(_property(),))),
    (DcalScope, lambda: DcalScope(tenant_id="tenant-1", ledger_id="ledger-1")),
    (TrustedBinding, _binding),
    (DurableIdentity, lambda: DurableIdentity(**_binding().model_dump(), action="append", idempotency_key="key-1")),
    (ProducerSignature, lambda: ProducerSignature(key_id="key-1", signature_b64url=_SIGNATURE)),
    (SubjectRef, lambda: SubjectRef(subject_id="subject:1")),
    (ProtectedEvidenceRef, lambda: ProtectedEvidenceRef(evidence_id="evidence:1", digest=_DIGEST)),
    (ProducerOperation, _operation),
    (DcalLogRecord, lambda: DcalLogRecord(record_id="record-1", sequence=0, commitment=_DIGEST)),
    (AppendDecision, lambda: AppendDecision(status="appended", record_id="record-1")),
    (AnchorDecision, lambda: AnchorDecision(status="anchored", evidence_id="evidence-1")),
    (SourceSnapshot, lambda: SourceSnapshot(snapshot_id="snapshot-1", snapshot_digest=_DIGEST)),
    (RecordPage, lambda: RecordPage(records=())),
)


@pytest.mark.parametrize(("model", "factory"), _FACTORIES)
def test_every_public_dto_is_frozen_strict_and_forbids_unknown_fields(
    model: type[BaseModel], factory: Callable[[], BaseModel],
) -> None:
    value = factory()
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["strict"] is True
    assert model.model_config["frozen"] is True
    with pytest.raises(ValidationError):
        model.model_validate({**value.model_dump(), "unknown": "no"})
    with pytest.raises(ValidationError):
        setattr(value, next(iter(model.model_fields)), None)


def test_dcal_base_dto_is_strict_and_forbids_unknown_fields() -> None:
    assert DcalDTO.model_config["frozen"] is True
    with pytest.raises(ValidationError):
        DcalDTO.model_validate({"unknown": "no"})


@pytest.mark.parametrize(("factory", "changes"), (
    (DcalCapabilities, {"features": ("signed_operations",) * 3}),
    (lambda **kw: DcalHealth(status="ready", **kw), {"healthy": "true"}),
    (_property, {"name": "x" * 65}),
    (lambda **kw: DcalConfigSchema(**kw), {"properties": (_property(),) * 33}),
    (lambda **kw: DcalScope(ledger_id="ledger-1", **kw), {"tenant_id": "x" * 129}),
    (_binding, {"policy_digest": "a" * 63}),
    (lambda **kw: DurableIdentity(**_binding().model_dump(), idempotency_key="key-1", **kw), {"action": "x" * 65}),
    (lambda **kw: ProducerSignature(key_id="key-1", **kw), {"signature_b64url": "A" * 87}),
    (SubjectRef, {"subject_id": "x" * 257}),
    (lambda **kw: ProtectedEvidenceRef(digest=_DIGEST, **kw), {"evidence_id": "x" * 257}),
    (_operation, {"subjects": (SubjectRef(subject_id="subject:1"),) * 257}),
    (lambda **kw: DcalLogRecord(record_id="record-1", commitment=_DIGEST, **kw), {"sequence": _MAX_SEQUENCE + 1}),
    (lambda **kw: AppendDecision(status="appended", **kw), {"record_id": "x" * 129}),
    (lambda **kw: SourceSnapshot(snapshot_digest=_DIGEST, **kw), {"snapshot_id": "x" * 129}),
    (lambda **kw: RecordPage(**kw), {"records": (DcalLogRecord(record_id="r", sequence=0, commitment=_DIGEST),) * 501}),
))
def test_dto_bounds_reject_oversized_values(factory: Callable[..., BaseModel], changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        factory(**changes)


def test_sequence_bounds_and_nested_raw_containers_are_rejected() -> None:
    assert DcalLogRecord(record_id="record-1", sequence=_MAX_SEQUENCE, commitment=_DIGEST).sequence == _MAX_SEQUENCE
    with pytest.raises(ValidationError):
        DcalLogRecord(record_id="record-1", sequence=-1, commitment=_DIGEST)
    with pytest.raises(ValidationError):
        _operation(profile="economy", subjects=[{"subject_id": "subject:1"}])
    with pytest.raises(ValidationError):
        _operation(signature={"key_id": "key-1", "signature_b64url": _SIGNATURE, "unknown": "no"})
    with pytest.raises(ValidationError):
        RecordPage(records=({"record_id": "record-1", "sequence": 0, "commitment": _DIGEST},))
    with pytest.raises(ValidationError):
        DcalConfigSchema(properties=({"name": "ledger_id", "value_type": "string", "required": True},))
    assert "profile" not in signature(ProducerOperation).parameters


def test_dcal_ports_are_independent_of_the_economy_ledger_port() -> None:
    assert LedgerPort not in DcalLedgerPort.__mro__
    assert LedgerPort not in ProvenanceLedgerPort.__mro__
    assert ProvenanceLedgerPort is DcalLedgerPort
    assert not set(DcalLedgerPort.__dict__).intersection({"create_wallet", "transfer", "mint", "post_bounty"})
    assert get_type_hints(DcalAnchorPort.anchor_finalized_checkpoint)["return"] is AnchorDecision
