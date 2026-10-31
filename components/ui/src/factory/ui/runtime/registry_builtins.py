"""Built-in component definitions for UI registry."""

from .models import ComponentType
from .registry_models import ComponentDefinition


def get_builtin_components() -> list[ComponentDefinition]:
    """Get list of built-in component definitions."""
    return [
        ComponentDefinition(
            component_type=ComponentType.TEXT, name="Text",
            description="Display text content with optional formatting",
            schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "variant": {"type": "string", "enum": ["h1", "h2", "h3", "body", "caption"]},
                },
                "required": ["content"],
            },
            default_props={"variant": "body"},
        ),
        ComponentDefinition(
            component_type=ComponentType.CHART, name="Chart",
            description="Display data visualizations (line, bar, pie, etc.)",
            schema={
                "type": "object",
                "properties": {
                    "chart_type": {"type": "string", "enum": ["line", "bar", "pie", "area", "scatter", "donut"]},
                    "data": {"type": "array"},
                    "title": {"type": "string"},
                    "x_axis": {"type": "string"},
                    "y_axis": {"type": "string"},
                },
                "required": ["chart_type", "data"],
            },
            default_props={"chart_type": "line"},
        ),
        ComponentDefinition(
            component_type=ComponentType.TABLE, name="Table",
            description="Display tabular data with optional sorting/filtering",
            schema={
                "type": "object",
                "properties": {
                    "columns": {"type": "array", "items": {"type": "object"}},
                    "rows": {"type": "array", "items": {"type": "object"}},
                    "sortable": {"type": "boolean"},
                    "filterable": {"type": "boolean"},
                },
                "required": ["columns", "rows"],
            },
            default_props={"sortable": True, "filterable": False},
        ),
        ComponentDefinition(
            component_type=ComponentType.FORM, name="Form",
            description="Interactive form with input fields",
            schema={
                "type": "object",
                "properties": {
                    "fields": {"type": "array", "items": {"type": "object"}},
                    "submit_label": {"type": "string"},
                    "action": {"type": "string"},
                },
                "required": ["fields"],
            },
            default_props={"submit_label": "Submit"},
        ),
        ComponentDefinition(
            component_type=ComponentType.METRIC, name="Metric",
            description="Display a single metric/KPI with optional trend",
            schema={
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": ["string", "number"]},
                    "unit": {"type": "string"},
                    "trend": {"type": "string", "enum": ["up", "down", "flat"]},
                    "trend_value": {"type": "string"},
                },
                "required": ["label", "value"],
            },
        ),
        ComponentDefinition(
            component_type=ComponentType.CARD, name="Card",
            description="Container card with title and content",
            schema={
                "type": "object",
                "properties": {"title": {"type": "string"}, "subtitle": {"type": "string"}, "content": {"type": "string"}},
            },
        ),
        ComponentDefinition(
            component_type=ComponentType.ALERT, name="Alert",
            description="Display alert/notification message",
            schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "success", "warning", "error"]},
                    "dismissible": {"type": "boolean"},
                },
                "required": ["message"],
            },
            default_props={"severity": "info", "dismissible": True},
        ),
        ComponentDefinition(
            component_type=ComponentType.PROGRESS, name="Progress",
            description="Display progress indicator",
            schema={
                "type": "object",
                "properties": {
                    "value": {"type": "number", "minimum": 0, "maximum": 100},
                    "label": {"type": "string"},
                    "variant": {"type": "string", "enum": ["linear", "circular"]},
                },
                "required": ["value"],
            },
            default_props={"variant": "linear"},
        ),
        ComponentDefinition(
            component_type=ComponentType.HERO, name="Hero",
            description="Full-width hero section with title, subtitle, and CTA",
            schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "cta_text": {"type": "string"},
                    "cta_href": {"type": "string"},
                    "image": {"type": "string"},
                    "overlay": {"type": "boolean"},
                },
                "required": ["title"],
            },
        ),
        ComponentDefinition(
            component_type=ComponentType.TABS, name="Tabs",
            description="Tabbed content container with Alpine.js transitions",
            schema={"type": "object", "required": ["tabs"], "properties": {
                "tabs": {"type": "array", "items": {"type": "object"}},
                "active": {"type": "string"},
            }},
        ),
        ComponentDefinition(
            component_type=ComponentType.BREADCRUMBS, name="Breadcrumbs",
            description="Navigation breadcrumb trail",
            schema={"type": "object", "required": ["items"], "properties": {
                "items": {"type": "array", "items": {"type": "object"}},
            }},
        ),
        ComponentDefinition(
            component_type=ComponentType.MODAL, name="Modal",
            description="Dialog modal with trigger button",
            schema={"type": "object", "required": ["title"], "properties": {
                "title": {"type": "string"}, "content": {"type": "string"},
                "trigger_label": {"type": "string"},
            }},
            default_props={"trigger_label": "Open"},
        ),
        ComponentDefinition(
            component_type=ComponentType.TOAST, name="Toast",
            description="Auto-dismissing notification toast",
            schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "type": {"type": "string", "enum": ["info", "success", "warning", "error"]},
                    "duration": {"type": "number"},
                    "dismissible": {"type": "boolean"},
                },
                "required": ["message"],
            },
            default_props={"type": "info", "duration": 5000, "dismissible": True},
        ),
        ComponentDefinition(
            component_type=ComponentType.ACTION_PANE, name="Action Pane",
            description="Polymorphic dropdown pane — one selector, dynamic form, shared result area",
            schema={
                "type": "object",
                "properties": {
                    "actions": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"}, "label": {"type": "string"},
                            "icon": {"type": "string"}, "tool": {"type": "string"},
                            "submit_label": {"type": "string"},
                            "fields": {"type": "array", "items": {"type": "object"}},
                        },
                        "required": ["id", "label", "tool", "fields"],
                    }},
                    "default_action": {"type": "string"},
                },
                "required": ["actions"],
            },
        ),
    ]
