"""Fresh S1 tests (epic #124): the lifecycle family spec registry.

Covers the registry-overlay merge contract: the versioned operation string
is the discriminator, explicit family never defers, unregistered operations
fall back to the first member (CAN), and unknown families fail loudly.
"""
from __future__ import annotations

import pytest

from factory.machine_learning.runtime.can_lifecycle_identity import (
    CONFORM_OPERATION, ISSUE_OPERATION, PROJECT_OPERATION, PROMOTE_OPERATION,
    TRAIN_OPERATION,
)
from factory.machine_learning.runtime.lifecycle_family import (
    CAN_FAMILY, DEFAULT_FAMILY, LifecycleFamilySpec, resolve_family,
)

_CAN_OPERATIONS = (
    TRAIN_OPERATION, ISSUE_OPERATION, CONFORM_OPERATION, PROMOTE_OPERATION,
    PROJECT_OPERATION,
)


def test_can_operations_resolve_via_operation_discriminator() -> None:
    """Every registered CAN operation string selects the CAN spec with no
    explicit family — the discriminator is the versioned operation string."""
    for operation in _CAN_OPERATIONS:
        spec = resolve_family(None, operation)
        assert spec.family == CAN_FAMILY
        assert spec.started_event == "ml.training.started"
        assert spec.terminal_event("completed") == "ml.training.completed"
        assert spec.terminal_event("failed") == "ml.training.failed"


def test_unregistered_operation_falls_back_to_first_member() -> None:
    """None + a not-yet-registered operation defers to the first registry
    member (CAN), so new families can be added without touching callers."""
    assert resolve_family(None, "ml.train-lor@v1").family == DEFAULT_FAMILY


def test_explicit_family_never_defers() -> None:
    """An explicit family id overrides the operation discriminator."""
    assert resolve_family(CAN_FAMILY, "ml.train-lor@v1").family == CAN_FAMILY


def test_unknown_family_fails_loudly() -> None:
    with pytest.raises(ValueError, match="unknown training lifecycle family"):
        resolve_family("nonexistent", TRAIN_OPERATION)


def test_unknown_terminal_status_fails_loudly() -> None:
    spec = resolve_family(None, TRAIN_OPERATION)
    with pytest.raises(ValueError, match="no terminal event"):
        spec.terminal_event("stopped")


def test_spec_is_frozen() -> None:
    spec = resolve_family(None, TRAIN_OPERATION)
    assert isinstance(spec, LifecycleFamilySpec)
    with pytest.raises(Exception):
        spec.started_event = "tampered"  # type: ignore[misc]
