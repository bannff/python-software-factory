"""UI exploration scenarios and actions.

Defines the structure for UI test scenarios that agents execute
via Chrome DevTools MCP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from abc import ABC, abstractmethod


@dataclass
class UIAction(ABC):
    """Base class for UI actions."""

    @property
    @abstractmethod
    def action_type(self) -> str:
        """Type identifier for this action."""
        ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        ...


@dataclass
class Click(UIAction):
    """Click on an element."""

    target: str  # uid from snapshot or selector
    double_click: bool = False
    timeout_ms: int = 5000

    @property
    def action_type(self) -> str:
        return "click"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "click",
            "target": self.target,
            "doubleClick": self.double_click,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class Fill(UIAction):
    """Fill a form field."""

    target: str  # uid or name attribute
    value: str
    timeout_ms: int = 5000

    @property
    def action_type(self) -> str:
        return "fill"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "fill",
            "target": self.target,
            "value": self.value,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class Hover(UIAction):
    """Hover over an element."""

    target: str
    timeout_ms: int = 5000

    @property
    def action_type(self) -> str:
        return "hover"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "hover",
            "target": self.target,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class WaitFor(UIAction):
    """Wait for text or element to appear."""

    text: str | None = None
    selector: str | None = None
    timeout_ms: int = 5000

    @property
    def action_type(self) -> str:
        return "wait"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "wait", "timeout_ms": self.timeout_ms}
        if self.text:
            result["text"] = self.text
        if self.selector:
            result["selector"] = self.selector
        return result


@dataclass
class Navigate(UIAction):
    """Navigate to a URL or use browser navigation."""

    url: str | None = None
    direction: Literal["back", "forward", "reload"] | None = None
    timeout_ms: int = 5000

    @property
    def action_type(self) -> str:
        return "navigate"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "navigate", "timeout_ms": self.timeout_ms}
        if self.url:
            result["url"] = self.url
        if self.direction:
            result["direction"] = self.direction
        return result


@dataclass
class PressKey(UIAction):
    """Press a key or key combination."""

    key: str  # e.g., "Enter", "Control+A", "Tab"
    timeout_ms: int = 5000

    @property
    def action_type(self) -> str:
        return "press_key"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "press_key",
            "key": self.key,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class UIScenario:
    """A complete UI exploration scenario."""

    id: str
    name: str
    route: str
    actions: list[UIAction] = field(default_factory=list)
    assertions: list[Any] = field(default_factory=list)  # UIAssertion
    description: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "route": self.route,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "assertions": [a.to_dict() for a in self.assertions],
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIScenario":
        """Create from dictionary (actions/assertions as raw dicts)."""
        return cls(
            id=data["id"],
            name=data["name"],
            route=data["route"],
            description=data.get("description", ""),
            actions=[],  # Would need action factory
            assertions=[],  # Would need assertion factory
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
