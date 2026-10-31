"""DaisyUI theme implementation.

Provides DaisyUI-compatible themes for the HTMX adapter.
DaisyUI themes use data-theme attribute and semantic color names.
"""

from typing import Any

from .base import Theme, ThemeConfig


# Built-in DaisyUI themes
DAISY_THEMES = [
    "light", "dark", "cupcake", "bumblebee", "emerald", "corporate",
    "synthwave", "retro", "cyberpunk", "valentine", "halloween", "garden",
    "forest", "aqua", "lofi", "pastel", "fantasy", "wireframe", "black",
    "luxury", "dracula", "cmyk", "autumn", "business", "acid", "lemonade",
    "night", "coffee", "winter", "dim", "nord", "sunset",
]


class DaisyTheme:
    """DaisyUI theme implementation.

    DaisyUI uses semantic color names that automatically adapt
    to the selected theme via data-theme attribute.
    """

    def __init__(self, theme_name: str = "light") -> None:
        if theme_name not in DAISY_THEMES:
            theme_name = "light"
        self._name = theme_name
        self._variant = "dark" if theme_name in _DARK_THEMES else "light"

    @property
    def name(self) -> str:
        return self._name

    @property
    def variant(self) -> str:
        return self._variant

    def get_config(self) -> ThemeConfig:
        """Get DaisyUI theme configuration."""
        return ThemeConfig(
            name=self._name,
            variant=self._variant,
            colors=self._get_semantic_colors(),
            spacing={"base": "1rem", "sm": "0.5rem", "lg": "1.5rem"},
            typography={"font-family": "system-ui, sans-serif"},
            borders={"radius": "var(--rounded-btn, 0.5rem)"},
            custom={"data_theme": self._name},
        )

    def get_css_variables(self) -> dict[str, str]:
        """DaisyUI uses data-theme, not CSS variables directly."""
        return {"--theme-name": self._name}

    def get_component_classes(self, component_type: str) -> dict[str, str]:
        """Get DaisyUI classes for component types."""
        class_map = {
            "button": {"base": "btn", "primary": "btn-primary", "secondary": "btn-secondary"},
            "card": {"base": "card bg-base-100 shadow-xl", "body": "card-body"},
            "alert": {"base": "alert", "info": "alert-info", "error": "alert-error"},
            "table": {"base": "table", "zebra": "table-zebra"},
            "input": {"base": "input input-bordered"},
            "progress": {"base": "progress", "primary": "progress-primary"},
            "badge": {"base": "badge", "primary": "badge-primary"},
            "modal": {"base": "modal", "box": "modal-box"},
            "navbar": {"base": "navbar bg-base-100"},
            "drawer": {"base": "drawer", "side": "drawer-side"},
        }
        return class_map.get(component_type, {"base": ""})

    def _get_semantic_colors(self) -> dict[str, str]:
        """Get DaisyUI semantic color names."""
        return {
            "primary": "primary",
            "secondary": "secondary",
            "accent": "accent",
            "neutral": "neutral",
            "base-100": "base-100",
            "base-200": "base-200",
            "base-300": "base-300",
            "info": "info",
            "success": "success",
            "warning": "warning",
            "error": "error",
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize theme."""
        return {
            "name": self._name,
            "variant": self._variant,
            "framework": "daisyui",
            "available_themes": DAISY_THEMES,
        }


# Themes that are considered "dark"
_DARK_THEMES = {
    "dark", "synthwave", "halloween", "forest", "black", "luxury",
    "dracula", "night", "coffee", "dim", "sunset",
}
