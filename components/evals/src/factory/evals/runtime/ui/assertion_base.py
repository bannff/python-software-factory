"""Base classes for UI assertions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from abc import ABC, abstractmethod


@dataclass
class AssertionResult:
    """Result of running an assertion."""

    passed: bool
    assertion_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class UIAssertion(ABC):
    """Base class for UI assertions."""

    @property
    @abstractmethod
    def assertion_type(self) -> str:
        """Type identifier for this assertion."""
        ...

    @abstractmethod
    def check(self, context: dict[str, Any]) -> AssertionResult:
        """Check the assertion against collected context.

        Args:
            context: Data collected during exploration including:
                - console_messages: List of console messages
                - network_requests: List of network requests
                - snapshot: A11y tree snapshot
                - performance: Performance trace data

        Returns:
            AssertionResult with pass/fail and details
        """
        ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        ...
