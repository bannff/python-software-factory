"""Fresh S2 tests: supervision outcomes owe their taxonomy to cancellation.

The supervision verbs live machine_learning-only (per the author note, the
agent-side registry surface is absent from this slice), but their outcome
taxonomy mirrors ManagedCancellationRegistry.outcome enums so the durable
cancellation semantics stay one discipline: requested / already-requested /
not-owner / not-found.
"""
from __future__ import annotations

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.can_lifecycle_identity import TRAIN_OPERATION
from factory.machine_learning.runtime.supervision_intents import (
    SupervisionError, SupervisionOwnershipError,
    UnknownSupervisedAttemptError, issue_supervision_intent,
)
from factory.agent.runtime.managed_cancellation import CancelOutcome


def _claim(store, attempt_id: str) -> None:
    claim, _ = store.claim(TRAIN_OPERATION, attempt_id, "b" * 64)
    assert claim == "created"


def test_outcome_taxonomy_mirrors_cancel_outcome(tmp_path) -> None:
    """Requested / replay / not-owner / not-found stay one naming family."""
    outcomes = set(CancelOutcome.__args__)
    assert outcomes == {"cancel_requested", "already_requested",
                        "not_owner", "not_found"}
    store = LocalCanLifecycleStore(tmp_path)
    _claim(store, "a1")
    fresh = issue_supervision_intent(store, TRAIN_OPERATION, "a1", "pause")
    replay = issue_supervision_intent(store, TRAIN_OPERATION, "a1", "pause")
    assert fresh["status"] == "pending" and replay == fresh
    try:
        issue_supervision_intent(store, "ml.issue-can-passports@v1", "a1", "pause")
    except SupervisionOwnershipError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected not_owner shape")
    try:
        issue_supervision_intent(store, TRAIN_OPERATION, "ghost", "pause")
    except UnknownSupervisedAttemptError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected not_found shape")
    assert UnknownSupervisedAttemptError.__bases__ == (SupervisionError,)
    assert SupervisionError.__bases__ == (ValueError,)

