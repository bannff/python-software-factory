"""React/shadcn transformation utilities.

Provides prop transformations, theme tokens, and animation hints
for the React adapter.
"""

from typing import Any

from ..models import ComponentType


# Mapping from our component types to shadcn component names
SHADCN_COMPONENT_MAP = {
    ComponentType.TEXT: "Typography",
    ComponentType.BUTTON: "Button",
    ComponentType.CARD: "Card",
    ComponentType.TABLE: "Table",
    ComponentType.METRIC: "Card",  # Composed with custom content
    ComponentType.ALERT: "Alert",
    ComponentType.PROGRESS: "Progress",
    ComponentType.FORM: "Form",
    ComponentType.LIST: "List",
    ComponentType.LINEAGE: "Lineage",
    ComponentType.CHART: "Chart",  # Would use recharts or similar
    ComponentType.IMAGE: "Image",
    ComponentType.HERO: "Card",  # Fallback: hero as full-width card
    ComponentType.TABS: "Tabs",
    ComponentType.BREADCRUMBS: "Breadcrumb",
    ComponentType.MODAL: "Dialog",
    ComponentType.TOAST: "Toast",
    ComponentType.PAGE: "Page",
    ComponentType.ACTION_PANE: "Card",
    ComponentType.CODE_BLOCK: "Code",
    ComponentType.TIMELINE: "Timeline",
    ComponentType.STAT_GRID: "Card",
    ComponentType.TREE_VIEW: "Tree",
    ComponentType.LIVE_FEED: "Card",
    ComponentType.COMPOSED_PAGE: "Page",
    ComponentType.GRAPH_VIEWER: "Custom",
    ComponentType.CHAT: "Card",
    ComponentType.ITEM_LIST: "Custom",
    ComponentType.STATUS_DOT: "Custom",
    ComponentType.TREND_BADGE: "Custom",
    ComponentType.SPARKLINE: "Custom",
    ComponentType.DETAIL_PANEL: "Custom",
    ComponentType.FILTER_BAR: "Custom",
    ComponentType.CUSTOM: "Custom",
}


def transform_props(ctype: ComponentType, props: dict[str, Any]) -> dict[str, Any]:
    """Transform props to shadcn conventions."""
    transformed = dict(props)

    # Map variant names to shadcn variants
    if "variant" in transformed:
        variant_map = {
            "primary": "default",
            "secondary": "secondary",
            "danger": "destructive",
            "warning": "outline",
            "info": "ghost",
        }
        transformed["variant"] = variant_map.get(
            transformed["variant"], transformed["variant"]
        )

    # Map severity to Alert variants
    if ctype == ComponentType.ALERT and "severity" in transformed:
        severity_map = {
            "info": "default",
            "success": "default",
            "warning": "warning",
            "error": "destructive",
        }
        transformed["variant"] = severity_map.get(
            transformed.pop("severity"), "default"
        )

    return transformed


def transform_layout(layout: dict[str, Any]) -> dict[str, Any]:
    """Transform layout to React-friendly format."""
    if not layout:
        return {"type": "stack", "direction": "vertical", "gap": 4}

    if layout.get("type") == "grid":
        cols = layout.get("columns", 1)
        gap = layout.get("gap", 4)
        return {
            "type": "grid",
            "columns": cols,
            "gap": gap,
            "className": f"grid grid-cols-{cols} gap-{gap}",
        }

    if layout.get("type") == "flex":
        direction = layout.get("direction", "row")
        gap = layout.get("gap", 4)
        return {
            "type": "flex",
            "direction": direction,
            "gap": gap,
            "className": f"flex flex-{direction} gap-{gap}",
        }

    return {"type": "stack", "direction": "vertical", "gap": 4}


def get_animation_hint(ctype: ComponentType, library: str) -> dict[str, Any] | None:
    """Get animation hints for Magic UI / Aceternity."""
    hints = {
        ComponentType.CARD: {"effect": "border-beam", "library": library},
        ComponentType.METRIC: {"effect": "number-ticker", "library": library},
        ComponentType.BUTTON: {"effect": "shimmer", "library": library},
        ComponentType.TEXT: {"effect": "text-reveal", "library": library},
        ComponentType.CHART: {"effect": "fade-in", "library": "framer-motion"},
        ComponentType.ALERT: {"effect": "slide-in", "library": "framer-motion"},
    }
    return hints.get(ctype)


# Theme color definitions (HSL values)
THEME_COLORS = {
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


def get_theme_tokens(theme_name: str) -> dict[str, str]:
    """Get shadcn theme tokens."""
    return THEME_COLORS.get(theme_name, THEME_COLORS["default"])
