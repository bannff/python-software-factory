"""A2UI Protocol support for agent-generated UI.

A2UI is Google's declarative JSON protocol where agents emit UI blueprints.
The client renders using native components.

Usage:
    from factory.ui.runtime.a2ui import A2UIParser, A2UIComponent, validate_a2ui

    # Parse A2UI payload from agent
    payload = {"components": [{"id": "1", "type": "Card", "props": {...}}]}
    components = A2UIParser.parse(payload)

    # Validate before rendering
    errors = validate_a2ui(payload)
"""

from .schema import A2UIComponent, A2UIPayload, validate_a2ui
from .components import COMPONENT_CATALOG, get_supported_components, is_supported_type
from .renderer import A2UIParser, a2ui_to_ui_view, ui_view_to_a2ui
from .actions import ActionRef, ActionRefError, parse_action_ref
from .action_normalize import (
    brick_of_view_tool, normalize_component_action, normalize_view_actions,
)

__all__ = [
    "A2UIComponent",
    "A2UIPayload",
    "ActionRef",
    "ActionRefError",
    "brick_of_view_tool",
    "normalize_component_action",
    "normalize_view_actions",
    "parse_action_ref",
    "validate_a2ui",
    "COMPONENT_CATALOG",
    "get_supported_components",
    "is_supported_type",
    "A2UIParser",
    "a2ui_to_ui_view",
    "ui_view_to_a2ui",
]
