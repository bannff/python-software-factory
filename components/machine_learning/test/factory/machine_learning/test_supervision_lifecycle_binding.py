"""Fresh S2 tests: chained attempt ids against the attempt-binding gym.

The adjustment chain (parent → adjusted child → grandchild) must obey the
same deterministic-binding discipline the durable-workflow gym pins:
attempt ids are derived from an unambiguous chain scope, the attempt input
is the exact canonical argument record, and a mismatched identity is
rejected loudly.
"""
from __future__ import annotations

from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.can_lifecycle_canonical import canonical_json
from factory.machine_learning.runtime.can_lifecycle_identity import TRAIN_OPERATION
from factory.machine_learning.runtime.supervision_claims import issue_adjustment_claim
from factory.workflow.runtime.attempt_binding import (
    DurableAttemptBindingError, verify_attempt_binding,
)

_OP = TRAIN_OPERATION


def _claim(store, attempt_id: str) -> None:
    claim, _ = store.claim(_OP, attempt_id, "b" * 64)
    assert claim == "created"


def expected_result(step_input_json: str) -> tuple[str, str]:
    from factory.workflow.runtime.attempt_binding import expected_attempt_binding
    return expected_attempt_binding(
        step_execution_id="ml.train-can-portfolio@v1:run1:slot",
        attempt_number=1, step_input_json=step_input_json,
        idempotency_argument=None,
    )


def test_gym_pins_deterministic_chained_attempt_identity(tmp_path) -> None:
    """Chain scope + canonical input pins exactly one attempt id, or fails."""
    step_input_json = canonical_json({
        "attempt_id": "slot", "adjusted_hyperparams": {"epochs": 12},
    }).decode()
    expected_id, expected_input = expected_result(step_input_json)
    verify_attempt_binding(
        step_execution_id="ml.train-can-portfolio@v1:run1:slot", attempt_number=1,
        attempt_id=expected_id, attempt_input_json=step_input_json,
        step_input_json=step_input_json, idempotency_argument=None,
        expected_number=1,
    )
    try:
        verify_attempt_binding(
            step_execution_id="ml.train-can-portfolio@v1:run1:slot", attempt_number=1,
            attempt_id=expected_id + "x", attempt_input_json=step_input_json,
            step_input_json=step_input_json, idempotency_argument=None,
            expected_number=1,
        )
    except DurableAttemptBindingError:
        pass
    else:  # pragma: no cover
        raise AssertionError("gym must reject a rebound attempt id")


def test_adjustment_chain_walks_deterministic_distinct_attempts(tmp_path) -> None:
    """adjust walks parent → child → grandchild with reproducible ids."""
    store = LocalCanLifecycleStore(tmp_path)
    _claim(store, "run1")
    child = issue_adjustment_claim(store, _OP, "run1", {"epochs": 12})
    child_id = child["adjusted_attempt_id"]
    again = issue_adjustment_claim(store, _OP, "run1", {"epochs": 12})
    assert again["adjusted_attempt_id"] == child_id
    grand = issue_adjustment_claim(store, _OP, child_id, {"epochs": 12, "lr": 0.1})
    assert grand["adjusted_attempt_id"] != child_id
    rebuilt = issue_adjustment_claim(store, _OP, child_id, {"epochs": 12, "lr": 0.1})
    assert rebuilt["adjusted_attempt_id"] == grand["adjusted_attempt_id"]
    assert store.load(_OP, child_id).state == "claimed"
    assert store.load(_OP, "run1").request_sha256 == "b" * 64

