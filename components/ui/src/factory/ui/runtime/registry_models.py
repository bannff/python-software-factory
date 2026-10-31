"""Component definition models for UI registry."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .models import ComponentType


@dataclass
class ComponentDefinition:
    """Definition of a registered component type."""
    component_type: ComponentType
    name: str
    description: str
    schema: dict[str, Any]
    default_props: dict[str, Any] = field(default_factory=dict)
    default_styles: dict[str, str] = field(default_factory=dict)
    validator: Callable[[dict[str, Any]], bool] | None = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.component_type.value,
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
            "default_props": self.default_props,
            "default_styles": self.default_styles,
            "registered_at": self.registered_at.isoformat(),
        }
