"""Closed, version-bound manifest condition factory."""
from __future__ import annotations

from typing import Any

from .behavior_registry import verify_condition
from .descriptors import ConditionDescriptor


def build_condition(descriptor: ConditionDescriptor | None):
    if descriptor is None:
        return None
    predecessors = verify_condition(descriptor)

    def all_predecessors_valid(
        state: Any, *, invocation_state: dict[str, Any] | None = None, **_: Any,
    ) -> bool:
        results = getattr(state, "results", {})
        return all(
            predecessor in results
            and str(getattr(results[predecessor], "status", "")).lower().endswith("completed")
            for predecessor in predecessors
        )

    return all_predecessors_valid


__all__ = ["build_condition"]
