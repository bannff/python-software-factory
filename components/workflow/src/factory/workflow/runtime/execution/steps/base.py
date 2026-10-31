"""Base types for step handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StepResult:
    """Result of executing a step."""
    done: bool  # True if workflow should stop (succeeded/failed/waiting)
    next_step_id: str | None  # Next step to execute, or None if done
    transition: dict[str, Any]  # Transition record for logging
    status: str | None = None  # New run status if changed
    result: dict[str, Any] | None = None  # Run result if completed
    error: str | None = None  # Error message if failed
    effect_owned: bool = True  # Caller owns the semantic transition/effect
