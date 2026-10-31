"""Versioned lifecycle family specs — the polymorphic training coordinator registry.

Keyed on the versioned operation string (the family discriminator); the CAN
family is the first member. Resolution is a registry-overlay merge — an
explicit family argument wins, otherwise the versioned operation string
selects the family, otherwise the first member applies:
no ``if domain ==`` branching may live outside this module (epic #124 S1).
"""
from __future__ import annotations

from dataclasses import dataclass

from .can_lifecycle_identity import (
    CONFORM_OPERATION, ISSUE_OPERATION, PROJECT_OPERATION, PROMOTE_OPERATION,
    TRAIN_OPERATION,
)

CAN_FAMILY = "can"
DEFAULT_FAMILY = CAN_FAMILY


@dataclass(frozen=True)
class LifecycleFamilySpec:
    """Event names one training lifecycle family emits at its chokepoints."""

    family: str
    started_event: str
    terminal_events: dict[str, str]

    def terminal_event(self, status: str) -> str:
        try:
            return self.terminal_events[status]
        except KeyError as exc:
            raise ValueError(
                f"lifecycle family {self.family} has no terminal event for {status!r}"
            ) from exc


CAN_SPEC = LifecycleFamilySpec(
    family=CAN_FAMILY,
    started_event="ml.training.started",
    terminal_events={
        "completed": "ml.training.completed", "failed": "ml.training.failed",
    },
)

_LIFECYCLE_FAMILIES: dict[str, LifecycleFamilySpec] = {CAN_FAMILY: CAN_SPEC}

# Registry overlay: versioned operation string → family id.
_OPERATION_FAMILIES: dict[str, str] = {
    TRAIN_OPERATION: CAN_FAMILY, ISSUE_OPERATION: CAN_FAMILY,
    CONFORM_OPERATION: CAN_FAMILY, PROMOTE_OPERATION: CAN_FAMILY,
    PROJECT_OPERATION: CAN_FAMILY,
}


def resolve_family(
    family: str | None, operation: str,
) -> LifecycleFamilySpec:
    """Registry-overlay merge for one lifecycle run's spec.

    ``family=None`` defers to the versioned operation string (the
    discriminator); unregistered operations fall back to the first member.
    An explicit family id never defers. Unknown family ids fail loudly.
    """
    key = (
        family if family is not None
        else _OPERATION_FAMILIES.get(operation, DEFAULT_FAMILY)
    )
    try:
        return _LIFECYCLE_FAMILIES[key]
    except KeyError:
        raise ValueError(f"unknown training lifecycle family: {key}") from None


__all__ = [
    "CAN_FAMILY", "CAN_SPEC", "DEFAULT_FAMILY", "LifecycleFamilySpec",
    "resolve_family",
]
