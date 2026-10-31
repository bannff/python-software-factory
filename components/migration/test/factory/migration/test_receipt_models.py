"""Property + unit tests for migration receipt/plan identity models.

Covers bounded grammar, credential-shape rejection, frozen immutability,
extra-field rejection, and the terminal-outcome settled contract.
"""
from __future__ import annotations

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from factory.migration.runtime.receipt_models import (
    CommitStatus, ImportOutcome, ImportReceipt, PageCursor, PlanIdentity,
    credential_clean,
)

_T, _O = "tenant-1", "owner-1"
_FP = "sha256:" + "a" * 32
_DIGEST = "sha256:" + "b" * 32


def _receipt(**over) -> ImportReceipt:
    base = dict(
        tenant_id=_T, owner_id=_O, adapter="kirocrew-v1",
        source_fingerprint=_FP, kind="memory", source_record_id="rec-1",
        target_digest=_DIGEST, outcome=ImportOutcome.IMPORTED,
    )
    base.update(over)
    return ImportReceipt(**base)


def _plan(**over) -> PlanIdentity:
    base = dict(tenant_id=_T, owner_id=_O, adapter="kirocrew-v1",
                source_fingerprint=_FP, plan_digest=_DIGEST, kinds=("memory", "lessons"))
    base.update(over)
    return PlanIdentity(**base)


def test_valid_models_construct() -> None:
    assert _receipt().outcome is ImportOutcome.IMPORTED
    assert _plan().kinds == ("memory", "lessons")
    cur = PageCursor(tenant_id=_T, owner_id=_O, adapter="kirocrew-v1",
                     source_fingerprint=_FP, plan_digest=_DIGEST,
                     kind="memory", page_index=0)
    assert cur.revision == 1


@pytest.mark.parametrize("bad", ["Memory", "has space", "-lead", "a" * 65, "", "mem,ory"])
def test_kind_grammar_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        _receipt(kind=bad)


@pytest.mark.parametrize("bad", ["Adapter", "under_score OK".upper(), "x y", "z" * 65, ""])
def test_adapter_grammar_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        _receipt(adapter=bad)


@pytest.mark.parametrize("bad", ["notadigest", "sha256:XYZ", "sha256:" + "a" * 8, ":deadbeef" * 2])
def test_target_digest_grammar_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        _receipt(target_digest=bad)


@given(secret=st.sampled_from(["ghp_" + "a" * 30, "sk-" + "b" * 24, "xoxb-" + "1" * 12,
                               "AKIA" + "A" * 16]))
def test_credential_shapes_rejected_everywhere(secret: str) -> None:
    assert credential_clean(secret) is False
    with pytest.raises(ValidationError):
        _receipt(source_record_id=secret)
    with pytest.raises(ValidationError):
        _receipt(adapter=secret)


def test_reason_code_bounded_and_optional() -> None:
    assert _receipt(reason_code="").reason_code == ""
    assert _receipt(reason_code="unknown_version").reason_code == "unknown_version"
    with pytest.raises(ValidationError):
        _receipt(reason_code="has space")
    with pytest.raises(ValidationError):
        _receipt(reason_code="x" * 65)


def test_frozen_and_extra_forbidden() -> None:
    r = _receipt()
    with pytest.raises(ValidationError):
        r.outcome = ImportOutcome.FAILED  # frozen
    with pytest.raises(ValidationError):
        _receipt(surprise="x")  # extra forbid


def test_outcome_settled_contract() -> None:
    assert ImportOutcome.IMPORTED.is_settled
    assert ImportOutcome.SKIPPED.is_settled
    assert not ImportOutcome.FAILED.is_settled


def test_plan_rejects_bad_kind_and_digest() -> None:
    with pytest.raises(ValidationError):
        _plan(kinds=("Memory",))
    with pytest.raises(ValidationError):
        _plan(plan_digest="nope")


def test_commit_status_values() -> None:
    assert {s.value for s in CommitStatus} == {
        "committed", "replayed", "superseded", "conflict"}
