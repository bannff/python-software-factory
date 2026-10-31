"""Theme system for UI adapters.

Provides pluggable themes for different UI frameworks:
- DaisyUI themes for HTMX adapter
- shadcn theme tokens for React adapter
"""

from .base import Theme, ThemeConfig
from .daisy import DaisyTheme, DAISY_THEMES
from .shadcn import ShadcnTheme, SHADCN_THEMES

__all__ = [
    "Theme",
    "ThemeConfig",
    "DaisyTheme",
    "DAISY_THEMES",
    "ShadcnTheme",
    "SHADCN_THEMES",
]
