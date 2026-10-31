"""Deterministic exact-argument binding for durable task attempts."""
from __future__ import annotations

from typing import Any

from .canonical import canonical_json, canonical_loads
from .run_binding import DurableAttemptBindingError
from .task_ids import task_attempt_id


def expected_attempt_binding(
    *, step_execution_id: str, attempt_number: int,
    step_input_json: str, idempotency_argument: str | None,
) -> tuple[str, str]:
    """Build the only valid attempt ID and exact canonical argument record."""
    if attempt_number < 1:
        raise ValueError("attempt number must be positive")
    arguments = canonical_loads(step_input_json)
    if not isinstance(arguments, dict):
        raise ValueError("step input must be a JSON object")
    if canonical_json(arguments) != step_input_json:
        raise ValueError("step input is not canonical")
    attempt_id = task_attempt_id(step_execution_id, attempt_number)
    if idempotency_argument:
        if idempotency_argument in arguments:
            raise ValueError("idempotency argument collides with task payload")
        arguments[idempotency_argument] = attempt_id
    return attempt_id, canonical_json(arguments)


def verify_attempt_binding(
    *, step_execution_id: str, attempt_number: int,
    attempt_id: str, attempt_input_json: str, step_input_json: str,
    idempotency_argument: str | None, expected_number: int,
) -> None:
    """Reject any persisted attempt that is not the deterministic record."""
    if attempt_number != expected_number:
        raise DurableAttemptBindingError("durable attempt number sequence mismatch")
    try:
        expected_id, expected_input = expected_attempt_binding(
            step_execution_id=step_execution_id,
            attempt_number=attempt_number,
            step_input_json=step_input_json,
            idempotency_argument=idempotency_argument,
        )
    except (TypeError, ValueError) as exc:
        raise DurableAttemptBindingError(
            f"durable attempt base input is invalid: {exc}"
        ) from exc
    if attempt_id != expected_id:
        raise DurableAttemptBindingError(
            "durable attempt_id does not match deterministic attempt identity"
        )
    if attempt_input_json != expected_input:
        raise DurableAttemptBindingError(
            "durable attempt input does not match exact canonical arguments"
        )
