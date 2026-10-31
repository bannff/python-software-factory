"""First-party supervision intents over the training lifecycle store.

Epic #124 S2: pause / stop-at-checkpoint / resume commands mint durable
:dclass:`CanEffectIntent` records bound to a live attempt's canonical
request identity. Nothing here mutates an in-flight process: the
coordinator-side runner dispatches pending intents at its next barrier
tick via :func:`consume_supervision_intent`, and a terminal attempt stays
immutable evidence (commands against it are typed errors).
"""
from __future__ import annotations

from typing import Any

from .can_lifecycle_contracts import CanEffectIntent, CanEffectReceipt, with_digest
from .can_lifecycle_canonical import effect_identity
from .can_lifecycle_identity import (
    CONFORM_OPERATION, ISSUE_OPERATION, PROJECT_OPERATION, PROMOTE_OPERATION,
    TRAIN_OPERATION,
)
from .can_lifecycle_ports import CanLifecycleStore

TERMINAL_STATES = frozenset({"succeeded", "failed"})
SCOPING_OPERATIONS = (
    TRAIN_OPERATION, ISSUE_OPERATION, CONFORM_OPERATION,
    PROMOTE_OPERATION, PROJECT_OPERATION,
)

PAUSE_UNIT = "supervision.training-pause@v1"
STOP_UNIT = "supervision.training-stop@v1"
RESUME_UNIT = "supervision.training-resume@v1"
ADJUST_UNIT = "supervision.hyperparam-adjust@v1"
_ACTION_UNITS: dict[str, str] = {
    "pause": PAUSE_UNIT, "stop": STOP_UNIT, "resume": RESUME_UNIT,
}


class SupervisionError(ValueError):
    """Loud, typed supervision dispatch failure (mirrors CancelOutcome)."""


class UnknownSupervisedAttemptError(SupervisionError):
    """No attempt is stored under the supervision caller's operation scope."""


class SupervisionOwnershipError(SupervisionError):
    """The attempt is bound to a different lifecycle operation (not_owner)."""


class TerminalSupervisedAttemptError(SupervisionError):
    """The attempt already reached its terminal; supervision is closed."""


class SupervisionConflictError(SupervisionError):
    """A divergent supervision command already owns this attempt-action."""


def _scoped_record(
    store: CanLifecycleStore, operation: str, attempt_id: str,
):
    record = store.load(operation, attempt_id)
    if record is not None:
        return record
    for scope in SCOPING_OPERATIONS:
        if scope != operation and store.load(scope, attempt_id) is not None:
            raise SupervisionOwnershipError(
                f"attempt {attempt_id!r} is bound to lifecycle operation "
                f"{scope}; supervision from operation {operation} is rejected"
            )
    raise UnknownSupervisedAttemptError(
        f"unknown supervised attempt {attempt_id!r} under {operation}"
    )


def _intent_for(
    store: CanLifecycleStore, record, unit: str, inputs: dict[str, Any],
) -> tuple[str, CanEffectIntent]:
    effect_id = effect_identity(record.operation, record.request_sha256, unit)
    intent = with_digest(
        CanEffectIntent, schema_version="1.0", operation=record.operation,
        effect_id=effect_id,
        request_sha256=record.request_sha256, unit=unit,
        inputs=dict(inputs), intent_sha256="",
    )
    return effect_id, intent


def issue_supervision_intent(
    store: CanLifecycleStore, operation: str, attempt_id: str, action: str,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mint (or replay) one supervision command for a live attempt."""
    unit = _ACTION_UNITS.get(action)
    if unit is None:
        raise SupervisionError(f"unknown supervision action: {action!r}")
    record = _scoped_record(store, operation, attempt_id)
    if record.state in TERMINAL_STATES:
        raise TerminalSupervisedAttemptError(
            f"attempt {attempt_id!r} is already {record.state}; supervision is closed"
        )
    effect_id, intent = _intent_for(
        store, record, unit, {"attempt_id": attempt_id, **(inputs or {})},
    )
    with store.effect_lock(operation, effect_id):
        existing = store.load_intent(effect_id)
        if existing is not None:
            if existing.intent_sha256 != intent.intent_sha256:
                raise SupervisionConflictError(
                    f"{action} supervision for {attempt_id!r} already differs"
                )
        else:
            store.save_intent(intent)
        receipt = store.load_receipt(effect_id)
    return {
        "schema_version": "1.0", "operation": operation, "attempt_id": attempt_id,
        "action": action, "intent_id": effect_id,
        "intent_sha256": intent.intent_sha256,
        "status": "dispatched" if receipt is not None else "pending",
    }


def consume_supervision_intent(
    store: CanLifecycleStore, operation: str, attempt_id: str, action: str,
) -> dict[str, Any] | None:
    """Dispatch one pending command at the attempt's next barrier tick.

    Returns ``None`` when nothing is pending; replay returns the persisted
    receipt output and never re-dispatches.
    """
    unit = _ACTION_UNITS.get(action)
    if unit is None:
        raise SupervisionError(f"unknown supervision action: {action!r}")
    record = _scoped_record(store, operation, attempt_id)
    effect_id, _ = _intent_for(store, record, unit, {})
    # Lock the effect scope (not the whole-run attempt lock): intent and
    # receipt publishes are immutable-link objects, and the runner already
    # holds the attempt's authority lock — an authority lock here would
    # deadlock. The per-effect flock excludes the issuer's publish.
    with store.effect_lock(operation, effect_id):
        intent = store.load_intent(effect_id)
        if intent is None:
            return None
        receipt = store.load_receipt(effect_id)
        if receipt is not None:
            return {"status": "replayed", "output": receipt.output,
                    "intent_sha256": intent.intent_sha256}
        saved = store.save_receipt(with_digest(
            CanEffectReceipt, schema_version="1.0", effect_id=effect_id,
            intent_sha256=intent.intent_sha256,
            output={"attempt_id": attempt_id, "action": action,
                    "unit": unit, "status": "dispatched",
                    "command": intent.inputs},
            receipt_sha256="",
        ))
        return {"status": "dispatched", "output": saved.output,
                "intent_sha256": intent.intent_sha256}


def pending_supervision_intents(
    store: CanLifecycleStore, operation: str, attempt_id: str,
) -> list[dict[str, Any]]:
    """Diagnostic surface: every issued supervision command for an attempt."""
    record = _scoped_record(store, operation, attempt_id)
    rows: list[dict[str, Any]] = []
    for action, unit in sorted(_ACTION_UNITS.items()):
        effect_id, _ = _intent_for(store, record, unit, {})
        intent = store.load_intent(effect_id)
        if intent is None:
            continue
        receipt = store.load_receipt(effect_id)
        rows.append({
            "action": action, "intent_id": effect_id,
            "intent_sha256": intent.intent_sha256, "inputs": intent.inputs,
            "status": "dispatched" if receipt is not None else "pending",
        })
    return rows


__all__ = [
    "ADJUST_UNIT", "PAUSE_UNIT", "RESUME_UNIT", "STOP_UNIT",
    "SCOPING_OPERATIONS", "TERMINAL_STATES",
    "SupervisionConflictError", "SupervisionError", "SupervisionOwnershipError",
    "TerminalSupervisedAttemptError", "UnknownSupervisedAttemptError",
    "consume_supervision_intent", "issue_supervision_intent",
    "pending_supervision_intents", "_scoped_record",
]
