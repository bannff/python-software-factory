"""Hyperparam adjustment and the S2 supervision MCP-facing call surface.

:func:`issue_adjustment_claim` mints a brand-new attempt claim for an
adjusted rerun — it never rebinds the parent attempt's key (the
coordinator's conflict path stays untouched; the parent terminal is
immutable evidence). :class:`TrainingSupervision` is the thin request →
envelope surface the MCP verbs compose.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .adapters.local_can_lifecycle import LocalCanLifecycleStore
from .can_lifecycle_canonical import (
    canonical_json, effect_identity, semantic_request,
)
from .can_lifecycle_contracts import CanEffectIntent, CanEffectReceipt
from .can_lifecycle_contracts import CanLifecycleAttempt, with_digest
from .can_lifecycle_identity import TRAIN_OPERATION
from .can_lifecycle_ports import CanLifecycleStore
from .passport_config import configured_passport_root
from .supervision_intents import ADJUST_UNIT, SupervisionError, _scoped_record


def _hyperparam_fault(hyperparams: Any) -> str | None:
    if not isinstance(hyperparams, dict):
        return "adjusted hyperparams must be a mapping"
    if not hyperparams:
        return "adjusted hyperparams must be non-empty"
    if not all(isinstance(key, str) for key in hyperparams):
        return "adjusted hyperparam names must be strings"
    try:
        canonical_json(hyperparams)
    except (TypeError, ValueError):
        return "adjusted hyperparams must be exactly canonicalizable"
    return None


def adjusted_child_id(
    operation: str, parent: CanLifecycleAttempt, hyperparams: dict[str, Any],
) -> str:
    """Deterministic child attempt id for (parent identity, exact hyperparams)."""
    tree = canonical_json({
        "operation": operation, "parent_attempt_id": parent.attempt_id,
        "parent_request_sha256": parent.request_sha256,
        "hyperparams": hyperparams,
    })
    return "adjusted-" + hashlib.sha256(tree).hexdigest()[:16]


def issue_adjustment_claim(
    store: CanLifecycleStore, operation: str, attempt_id: str,
    hyperparams: dict[str, Any],
) -> dict[str, Any]:
    """Mint the deterministic child attempt claim for an adjusted rerun.

    The child claim is keyed on (parent identity, exact hyperparams), so a
    repeated identical adjustment replays the same claim; a divergent
    adjustment mints a different attempt. The parent record is never
    written.
    """
    fault = _hyperparam_fault(hyperparams)
    if fault is not None:
        raise SupervisionError(fault)
    parent = _scoped_record(store, operation, attempt_id)
    child_id = adjusted_child_id(operation, parent, hyperparams)
    child_request = {
        "attempt_id": child_id, "parent_attempt_id": attempt_id,
        "adjusted_hyperparams": hyperparams,
    }
    _, child_sha = semantic_request(operation, child_request, {"self": operation})
    unit = ADJUST_UNIT + "#" + child_id
    with store.lock(operation, child_id):
        resolution, record = store.claim(operation, child_id, child_sha)
        if resolution == "conflict":
            return {
                "schema_version": "1.0", "operation": operation,
                "status": "conflict", "attempt_id": child_id,
                "error": "adjusted attempt key is already bound to a different request",
            }
    adjustment = with_digest(
        CanEffectIntent, schema_version="1.0", operation=operation,
        effect_id=effect_identity(operation, parent.request_sha256, unit),
        request_sha256=parent.request_sha256, unit=ADJUST_UNIT,
        inputs={
            "attempt_id": attempt_id, "adjusted_attempt_id": child_id,
            "hyperparams": hyperparams, "adjusted_request_sha256": child_sha,
        },
        intent_sha256="",
    )
    return _with_evidence(
        store, parent, adjustment, record, child_id, child_sha, hyperparams,
    )


def _with_evidence(
    store: CanLifecycleStore, parent: CanLifecycleAttempt,
    adjustment: CanEffectIntent, record: CanLifecycleAttempt,
    child_id: str, child_sha: str, hyperparams: dict[str, Any],
) -> dict[str, Any]:
    with store.effect_lock(adjustment.operation, adjustment.effect_id):
        existing = store.load_intent(adjustment.effect_id)
        if existing is not None:
            if existing.intent_sha256 != adjustment.intent_sha256:
                raise SupervisionError(
                    f"adjustment evidence for {child_id!r} already differs"
                )
        else:
            store.save_intent(adjustment)
            store.save_receipt(with_digest(
                CanEffectReceipt, schema_version="1.0", effect_id=adjustment.effect_id,
                intent_sha256=adjustment.intent_sha256,
                output={"status": "minted", "attempt_id": parent.attempt_id,
                        "adjusted_attempt_id": child_id},
                receipt_sha256="",
            ))
    return {
        "schema_version": "1.0",
        "status": "already_minted" if existing is not None else "minted",
        "operation": parent.operation,
        "parent_attempt_id": parent.attempt_id,
        "adjusted_attempt_id": child_id, "adjusted_request_sha256": child_sha,
        "claim_state": record.state, "hyperparams": hyperparams,
    }


class TrainingSupervision:
    """Thin request → envelope surface over one lifecycle store."""

    def __init__(self, store: CanLifecycleStore) -> None:
        self._store = store

    def pause(self, *, attempt_id: str, reason: str = "") -> dict[str, Any]:
        from .supervision_intents import issue_supervision_intent
        return issue_supervision_intent(
            self._store, TRAIN_OPERATION, str(attempt_id), "pause",
            {"reason": str(reason)},
        )

    def stop(self, *, attempt_id: str, checkpoint_name: str = "") -> dict[str, Any]:
        from .supervision_intents import issue_supervision_intent
        return issue_supervision_intent(
            self._store, TRAIN_OPERATION, str(attempt_id), "stop",
            {"checkpoint_name": str(checkpoint_name)},
        )

    def resume(self, *, attempt_id: str, reason: str = "") -> dict[str, Any]:
        from .supervision_intents import issue_supervision_intent
        return issue_supervision_intent(
            self._store, TRAIN_OPERATION, str(attempt_id), "resume",
            {"reason": str(reason)},
        )

    def adjust(self, *, attempt_id: str, hyperparams: dict[str, Any]) -> dict[str, Any]:
        return issue_adjustment_claim(
            self._store, TRAIN_OPERATION, str(attempt_id), dict(hyperparams),
        )


def create_training_supervision(
    root: str | Path | None = None,
) -> TrainingSupervision:
    """Compose the supervision surface on the CAN lifecycle trust root."""
    return TrainingSupervision(LocalCanLifecycleStore(configured_passport_root(root)))


__all__ = [
    "TrainingSupervision", "adjusted_child_id", "create_training_supervision",
    "issue_adjustment_claim",
]
