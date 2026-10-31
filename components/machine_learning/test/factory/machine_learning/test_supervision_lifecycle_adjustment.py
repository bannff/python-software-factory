"""Fresh S2 tests (epic #124): adjustment claims and typed error shapes.

``ml_adjust_hyperparam`` issues a NEW attempt claim keyed on (parent
identity, exact hyperparams); the parent's record/terminal is immutable
evidence and is never rebound (the coordinator's conflict path stays
undisturbed). Error shapes mirror ManagedCancellationRegistry outcomes.
"""
from __future__ import annotations

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.can_lifecycle_identity import TRAIN_OPERATION
from factory.machine_learning.runtime.supervision_claims import issue_adjustment_claim
from factory.machine_learning.runtime.supervision_intents import (
    SupervisionOwnershipError, TerminalSupervisedAttemptError,
    UnknownSupervisedAttemptError, issue_supervision_intent,
)

_OP = TRAIN_OPERATION


def _claim(store, attempt_id: str, request_sha: str = "b" * 64) -> None:
    claim, _ = store.claim(_OP, attempt_id, request_sha)
    assert claim == "created"


def _terminal(store, attempt_id: str, status: str = "completed") -> dict:
    _claim(store, attempt_id, "c" * 64)
    record = store.load(_OP, attempt_id)
    terminal = {"schema_version": "1.0", "operation": _OP,
                "status": status, "attempt_id": attempt_id,
                "request_sha256": "c" * 64, "can_ids": ["c1"]}
    published = store.publish(record, terminal)
    return store.load_terminal(published)


def test_adjust_after_completed_attempt_issues_new_claim(tmp_path) -> None:
    """A terminal parent stays terminal; adjust mints a fresh child claim."""
    store = LocalCanLifecycleStore(tmp_path)
    _terminal(store, "run1")
    result = issue_adjustment_claim(store, _OP, "run1", {"epochs": 12})
    assert result["status"] == "minted"
    child_id = result["adjusted_attempt_id"]
    parent = store.load(_OP, "run1")
    child = store.load(_OP, child_id)
    assert result["claim_state"] == "claimed"
    assert parent.state == "succeeded" and child.state == "claimed"
    assert child.request_sha256 == result["adjusted_request_sha256"]


def test_repeat_adjust_replays_same_child_and_divergence_mints_new(tmp_path) -> None:
    """Same (parent, hyperparams) → same claim; divergent → different claim."""
    store = LocalCanLifecycleStore(tmp_path)
    _claim(store, "run1")
    first = issue_adjustment_claim(store, _OP, "run1", {"epochs": 12})
    repeat = issue_adjustment_claim(store, _OP, "run1", {"epochs": 12})
    divergent = issue_adjustment_claim(store, _OP, "run1", {"epochs": 13})
    assert first["status"] == "minted"
    assert repeat["status"] == "already_minted"
    assert repeat["adjusted_attempt_id"] == first["adjusted_attempt_id"]
    assert divergent["status"] == "minted"
    assert divergent["adjusted_attempt_id"] != first["adjusted_attempt_id"]


def test_adjustment_error_shapes_are_typed(tmp_path) -> None:
    """Unknown attempt and wrong-caller (cross-operation) shapes stay typed."""
    store = LocalCanLifecycleStore(tmp_path)
    _claim(store, "run1")
    _terminal(store, "done1", status="failed")
    try:
        issue_adjustment_claim(store, _OP, "ghost", {"epochs": 1})
    except UnknownSupervisedAttemptError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected UnknownSupervisedAttemptError")
    try:
        issue_supervision_intent(
            store, "ml.issue-can-passports@v1", "run1", "pause",
        )
    except SupervisionOwnershipError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected SupervisionOwnershipError")
    try:
        issue_adjustment_claim(store, _OP, "never", {"epochs": 1})
    except UnknownSupervisedAttemptError:
        pass
    try:
        issue_supervision_intent(store, _OP, "done1", "resume")
    except TerminalSupervisedAttemptError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected TerminalSupervisedAttemptError")


