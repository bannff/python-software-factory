"""Authority projection must ignore the per-call idempotency correlation.

Regression for the M7.6 dogfood hang's second bug: ``NativeEnvelopeInvoker``
stamps ``attributes.workflow_attempt_id`` with each call's own
``idempotency_key``. The run's ``initiation_envelope`` therefore carries the
enroll call's ``run_key`` while the background drive's later ``resume_run``
carries ``background-drive:<run_id>`` — a legitimate difference that must NOT
be read as an authority mismatch. Real identity differences must still reject.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.workflow.runtime.authority import (
    AuthorityMismatchError, execution_envelope,
)
from factory.workflow.runtime.envelope import Envelope


def _run(initiation: Envelope) -> SimpleNamespace:
    # execution_envelope only enforces authority for named (versioned) runs.
    return SimpleNamespace(workflow_version_id="wv-1", initiation_envelope=initiation)


def test_differing_only_by_workflow_attempt_id_is_the_same_authority() -> None:
    initiation = Envelope(
        tenant_id="local", principal_id="kiro-agent", session_id="t-1",
        attributes={"workflow_attempt_id": "run-key-enroll"},
    )
    action = Envelope(
        tenant_id="local", principal_id="kiro-agent", session_id="t-1",
        attributes={"workflow_attempt_id": "background-drive:wfr:v1:abc"},
    )
    # Must not raise; returns the frozen initiation context.
    assert execution_envelope(_run(initiation), action) is initiation


def test_real_identity_difference_still_rejects() -> None:
    initiation = Envelope(
        tenant_id="local", principal_id="kiro-agent", session_id="t-1",
        attributes={"workflow_attempt_id": "run-key-enroll"},
    )
    action = Envelope(
        tenant_id="local", principal_id="someone-else", session_id="t-1",
        attributes={"workflow_attempt_id": "run-key-enroll"},
    )
    with pytest.raises(AuthorityMismatchError):
        execution_envelope(_run(initiation), action)
