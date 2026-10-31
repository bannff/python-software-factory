"""Base theme abstractions.

Defines the Protocol for themes and common configuration.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ThemeConfig:
    """Configuration for a theme."""

    name: str
    variant: str = "default"  # light, dark, etc.
    colors: dict[str, str] = field(default_factory=dict)
    spacing: dict[str, str] = field(default_factory=dict)
    typography: dict[str, str] = field(default_factory=dict)
    borders: dict[str, str] = field(default_factory=dict)
    shadows: dict[str, str] = field(default_factory=dict)
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "variant": self.variant,
            "colors": self.colors,
            "spacing": self.spacing,
            "typography": self.typography,
            "borders": self.borders,
            "shadows": self.shadows,
            "custom": self.custom,
        }


@runtime_checkable
class Theme(Protocol):
    """Protocol for UI themes.

    Themes provide styling tokens that adapters use to render components.
    Different adapters may interpret these tokens differently.
    """

    @property
    def name(self) -> str:
        """Theme identifier."""
        ...

    @property
    def variant(self) -> str:
        """Theme variant (light, dark, etc.)."""
        ...

    def get_config(self) -> ThemeConfig:
        """Get full theme configuration."""
        ...

    def get_css_variables(self) -> dict[str, str]:
        """Get CSS variable definitions."""
        ...

    def get_component_classes(self, component_type: str) -> dict[str, str]:
        """Get CSS classes for a component type."""
        ...
