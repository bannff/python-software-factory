"""shadcn/ui theme implementation.

Provides shadcn-compatible theme tokens for the React adapter.
shadcn uses CSS variables with HSL color values.
"""

from typing import Any

from .base import Theme, ThemeConfig


# Built-in shadcn themes
SHADCN_THEMES = ["default", "dark", "slate", "stone", "gray", "neutral", "red", "rose", "orange", "green", "blue", "yellow", "violet"]


class ShadcnTheme:
    """shadcn/ui theme implementation.

    shadcn uses CSS variables with HSL values for theming.
    This allows easy customization and dark mode support.
    """

    def __init__(self, theme_name: str = "default") -> None:
        self._name = theme_name if theme_name in SHADCN_THEMES else "default"
        self._variant = "dark" if theme_name == "dark" else "light"

    @property
    def name(self) -> str:
        return self._name

    @property
    def variant(self) -> str:
        return self._variant

    def get_config(self) -> ThemeConfig:
        """Get shadcn theme configuration."""
        colors = _THEME_COLORS.get(self._name, _THEME_COLORS["default"])
        return ThemeConfig(
            name=self._name,
            variant=self._variant,
            colors=colors,
            spacing={"base": "1rem", "sm": "0.5rem", "lg": "1.5rem", "xl": "2rem"},
            typography={"font-family": "Inter, system-ui, sans-serif"},
            borders={"radius": "0.5rem"},
            shadows={"sm": "0 1px 2px 0 rgb(0 0 0 / 0.05)"},
        )

    def get_css_variables(self) -> dict[str, str]:
        """Get CSS variable definitions for shadcn."""
        colors = _THEME_COLORS.get(self._name, _THEME_COLORS["default"])
        return {f"--{k}": v for k, v in colors.items()}

    def get_component_classes(self, component_type: str) -> dict[str, str]:
        """Get Tailwind classes for shadcn components."""
        # shadcn components use Tailwind utility classes
        class_map = {
            "button": {
                "base": "inline-flex items-center justify-center rounded-md text-sm font-medium",
                "default": "bg-primary text-primary-foreground hover:bg-primary/90",
                "destructive": "bg-destructive text-destructive-foreground hover:bg-destructive/90",
                "outline": "border border-input bg-background hover:bg-accent",
                "ghost": "hover:bg-accent hover:text-accent-foreground",
            },
            "card": {
                "base": "rounded-lg border bg-card text-card-foreground shadow-sm",
                "header": "flex flex-col space-y-1.5 p-6",
                "content": "p-6 pt-0",
            },
            "alert": {
                "base": "relative w-full rounded-lg border p-4",
                "default": "bg-background text-foreground",
                "destructive": "border-destructive/50 text-destructive",
            },
            "input": {"base": "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"},
            "table": {"base": "w-full caption-bottom text-sm", "header": "border-b", "row": "border-b"},
        }
        return class_map.get(component_type, {"base": ""})

    def to_dict(self) -> dict[str, Any]:
        """Serialize theme."""
        return {
            "name": self._name,
            "variant": self._variant,
            "framework": "shadcn",
            "css_variables": self.get_css_variables(),
            "available_themes": SHADCN_THEMES,
        }


# Theme color definitions (HSL values)
_THEME_COLORS = {
    "default": {
        "background": "0 0% 100%",
        "foreground": "222.2 84% 4.9%",
        "card": "0 0% 100%",
        "card-foreground": "222.2 84% 4.9%",
        "popover": "0 0% 100%",
        "popover-foreground": "222.2 84% 4.9%",
        "primary": "222.2 47.4% 11.2%",
        "primary-foreground": "210 40% 98%",
        "secondary": "210 40% 96.1%",
        "secondary-foreground": "222.2 47.4% 11.2%",
        "muted": "210 40% 96.1%",
        "muted-foreground": "215.4 16.3% 46.9%",
        "accent": "210 40% 96.1%",
        "accent-foreground": "222.2 47.4% 11.2%",
        "destructive": "0 84.2% 60.2%",
        "destructive-foreground": "210 40% 98%",
        "border": "214.3 31.8% 91.4%",
        "input": "214.3 31.8% 91.4%",
        "ring": "222.2 84% 4.9%",
    },
    "dark": {
        "background": "222.2 84% 4.9%",
        "foreground": "210 40% 98%",
        "card": "222.2 84% 4.9%",
        "card-foreground": "210 40% 98%",
        "popover": "222.2 84% 4.9%",
        "popover-foreground": "210 40% 98%",
        "primary": "210 40% 98%",
        "primary-foreground": "222.2 47.4% 11.2%",
        "secondary": "217.2 32.6% 17.5%",
        "secondary-foreground": "210 40% 98%",
        "muted": "217.2 32.6% 17.5%",
        "muted-foreground": "215 20.2% 65.1%",
        "accent": "217.2 32.6% 17.5%",
        "accent-foreground": "210 40% 98%",
        "destructive": "0 62.8% 30.6%",
        "destructive-foreground": "210 40% 98%",
        "border": "217.2 32.6% 17.5%",
        "input": "217.2 32.6% 17.5%",
        "ring": "212.7 26.8% 83.9%",
    },
}
