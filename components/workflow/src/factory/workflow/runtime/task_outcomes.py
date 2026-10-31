"""Pure classification of transport-successful named-MCP payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_json
from .task_models import PayloadPredicate, TaskOutcomePolicy
from .task_refs import resolve_pointer


@dataclass(frozen=True)
class OutcomeDecision:
    succeeded: bool
    continued: bool = False
    retryable: bool = False
    error: str | None = None


def _matches(output: Any, predicate: PayloadPredicate) -> bool:
    actual = resolve_pointer(output, predicate.pointer)
    return canonical_json(actual) == canonical_json(predicate.equals)


def classify_outcome(
    output: Any, policy: TaskOutcomePolicy | None,
) -> OutcomeDecision:
    """Apply a frozen payload policy, failing closed on missing success data."""
    if policy is None:
        return OutcomeDecision(True)
    try:
        matched = _matches(output, policy.success)
    except ValueError as exc:
        return OutcomeDecision(False, error=f"outcome success predicate unresolved: {exc}")
    if matched:
        return OutcomeDecision(True)
    if policy.continuation is not None:
        try:
            if _matches(output, policy.continuation):
                return OutcomeDecision(False, continued=True)
        except ValueError:
            pass
    retryable = False
    if policy.retryable is not None:
        try:
            retryable = _matches(output, policy.retryable)
        except ValueError:
            retryable = False
    error = f"outcome predicate did not match at {policy.success.pointer or '/'}"
    if policy.error_pointer is not None:
        try:
            value = resolve_pointer(output, policy.error_pointer)
            error = value if isinstance(value, str) else canonical_json(value)
        except ValueError:
            pass
    return OutcomeDecision(False, retryable=retryable, error=error)
