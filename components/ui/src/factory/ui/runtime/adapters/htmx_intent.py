"""Semantic intent helpers for HTMX renderers.

Bricks declare intent (e.g. "critical", "hero"), renderers
translate intent to visual treatment. This keeps design decisions
in the adapter layer, not in bricks.
"""

from ..models import UIComponent

# Border-left color coding (card pattern)
_INTENT_BORDER = {
    "hero": "border-l-4 border-l-primary",
    "critical": "border-l-4 border-l-error",
    "success": "border-l-4 border-l-success",
    "warning": "border-l-4 border-l-warning",
    "muted": "opacity-70",
}

# Gradient hero treatment for text blocks
_HERO_GRADIENT = (
    "bg-gradient-to-r from-primary to-secondary"
    " rounded-box text-primary-content p-8"
)

# Value color mapping for metrics
METRIC_VALUE_CLS = {
    "hero": "text-primary",
    "critical": "text-error",
    "success": "text-success",
    "warning": "text-warning",
    "": "",
}

# Stat-figure color mapping for metric icons
METRIC_FIGURE_CLS = {
    "hero": "text-primary",
    "critical": "text-error",
    "success": "text-success",
    "warning": "text-warning",
    "": "text-primary",
}


def intent_cls(c: UIComponent) -> str:
    """Return extra Tailwind classes based on semantic intent prop."""
    return _INTENT_BORDER.get(c.props.get("intent", ""), "")


def hero_gradient_cls(c: UIComponent) -> str:
    """Return gradient classes if intent is hero, else empty."""
    if c.props.get("intent") == "hero":
        return _HERO_GRADIENT
    return ""


def maybe_collapse(c: UIComponent, html: str, title: str = "") -> str:
    """Wrap HTML in a DaisyUI collapse if component requests it."""
    if not c.props.get("collapsible"):
        return html
    label = title or c.props.get("title", "")
    return (
        f'<div class="collapse collapse-arrow bg-base-200 rounded-box">'
        f'<input type="checkbox" checked />'
        f'<div class="collapse-title font-semibold">{label}</div>'
        f'<div class="collapse-content">{html}</div></div>'
    )
