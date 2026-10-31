"""A2UI Component catalog — supported types and their mappings to native UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import ComponentType


@dataclass
class ComponentSpec:
    """Specification for a supported A2UI component type."""

    a2ui_type: str
    native_type: ComponentType
    description: str
    required_props: list[str] = field(default_factory=list)
    optional_props: list[str] = field(default_factory=list)
    supports_children: bool = False


# A2UI component catalog - maps A2UI types to native UI components
COMPONENT_CATALOG: dict[str, ComponentSpec] = {
    "Card": ComponentSpec(
        a2ui_type="Card",
        native_type=ComponentType.CARD,
        description="Container with optional title and content",
        optional_props=["title", "subtitle", "variant", "elevation"],
        supports_children=True,
    ),
    "Text": ComponentSpec(
        a2ui_type="Text",
        native_type=ComponentType.TEXT,
        # bd-3hkqx r4 — FE accepts text|content|value (mem 487b3ec5).
        description="Text. Prop 'text' canonical; 'content'/'value' aliased.",
        required_props=["text"],
        optional_props=["variant", "size", "color", "align", "content", "value"],
    ),
    # bd:3jcls.3 — `action` is an ActionRef (a2ui/actions.py); Form's `method`
    # was REMOVED (an action may only name an MCP tool, never an HTTP verb).
    "Button": ComponentSpec(
        a2ui_type="Button", native_type=ComponentType.BUTTON,
        description="Clickable button. Prop 'action' is an ActionRef (MCP tool ref).",
        required_props=["label"],
        optional_props=["variant", "size", "disabled", "action", "icon"],
    ),
    "Form": ComponentSpec(
        a2ui_type="Form", native_type=ComponentType.FORM,
        description="Form container. Prop 'action' is an ActionRef (MCP tool ref).",
        optional_props=["action", "submitLabel", "fields", "title"],
        supports_children=True,
    ),
    "TextField": ComponentSpec(
        a2ui_type="TextField",
        native_type=ComponentType.CUSTOM,
        description="Text input field",
        required_props=["name"],
        optional_props=["label", "placeholder", "required", "type", "value"],
    ),
    "Select": ComponentSpec(
        a2ui_type="Select",
        native_type=ComponentType.CUSTOM,
        description="Dropdown selection",
        required_props=["name", "options"],
        optional_props=["label", "placeholder", "required", "value"],
    ),
    "DatePicker": ComponentSpec(
        a2ui_type="DatePicker",
        native_type=ComponentType.CUSTOM,
        description="Date selection input",
        required_props=["name"],
        optional_props=["label", "min", "max", "value"],
    ),
    "TimePicker": ComponentSpec(
        a2ui_type="TimePicker",
        native_type=ComponentType.CUSTOM,
        description="Time selection input",
        required_props=["name"],
        optional_props=["label", "min", "max", "value"],
    ),
    "Image": ComponentSpec(
        a2ui_type="Image",
        native_type=ComponentType.IMAGE,
        description="Image display",
        required_props=["src"],
        optional_props=["alt", "width", "height", "fit"],
    ),
    "List": ComponentSpec(
        a2ui_type="List",
        native_type=ComponentType.LIST,
        description="List of items",
        optional_props=["items", "ordered", "variant"],
        supports_children=True,
    ),
    "Table": ComponentSpec(
        a2ui_type="Table",
        native_type=ComponentType.TABLE,
        description="Data table",
        required_props=["columns", "rows"],
        optional_props=["sortable", "paginated", "pageSize"],
    ),
    "Chart": ComponentSpec(
        a2ui_type="Chart",
        native_type=ComponentType.CHART,
        description="Data visualization chart",
        required_props=["chartType", "data"],
        optional_props=["title", "legend", "colors"],
    ),
    "Alert": ComponentSpec(
        a2ui_type="Alert",
        native_type=ComponentType.ALERT,
        # bd-3hkqx r4 — FE accepts message|description (mem 487b3ec5).
        description="Alert. Prop 'message' or 'description' for body.",
        required_props=[],
        optional_props=["message", "description", "title", "severity",
                         "variant", "dismissible", "icon"],
    ),
    "Progress": ComponentSpec(
        a2ui_type="Progress",
        native_type=ComponentType.PROGRESS,
        description="Progress indicator",
        optional_props=["value", "max", "variant", "label"],
    ),
    "Metric": ComponentSpec(
        a2ui_type="Metric", native_type=ComponentType.METRIC,
        description="Single metric display", required_props=["value"],
        optional_props=["label", "unit", "trend", "trendValue", "data_tool", "data_path"],
    ),
    "Lineage": ComponentSpec(
        a2ui_type="Lineage", native_type=ComponentType.LINEAGE,
        description="Neutral evidence-backed lineage",
        optional_props=["data", "data_tool", "data_path", "nodes", "edges", "missing_links", "empty_message"],
    ),
    "Divider": ComponentSpec(
        a2ui_type="Divider",
        native_type=ComponentType.CUSTOM,
        description="Visual separator",
        optional_props=["orientation", "variant"],
    ),
    "Spacer": ComponentSpec(
        a2ui_type="Spacer",
        native_type=ComponentType.CUSTOM,
        description="Empty space",
        optional_props=["size"],
    ),
    "ItemList": ComponentSpec(
        a2ui_type="ItemList", native_type=ComponentType.ITEM_LIST,
        description="Rich filterable list with per-item detail drill-down",
        required_props=["data_tool", "item_key"],
        optional_props=["empty_icon", "empty_message", "header", "filters",
                         "item_layout", "item_snapshot_tool", "item_snapshot_args",
                         "snapshot_merge_path", "detail", "live_state_path",
                         "page_size", "sort_fields", "refresh_interval_ms"],
    ),
    "StatusDot": ComponentSpec(
        a2ui_type="StatusDot", native_type=ComponentType.STATUS_DOT,
        description="Threshold-based colored status indicator dot",
        required_props=["value", "thresholds"], optional_props=["colors"],
    ),
    "TrendBadge": ComponentSpec(
        a2ui_type="TrendBadge", native_type=ComponentType.TREND_BADGE,
        description="Direction arrow with optional percentage change",
        required_props=["direction"], optional_props=["change_pct", "positive_is_good"],
    ),
    "Sparkline": ComponentSpec(
        a2ui_type="Sparkline", native_type=ComponentType.SPARKLINE,
        description="Inline mini bar or line chart from numeric array",
        required_props=["data"], optional_props=["variant", "color", "height", "max_points"],
    ),
    "DetailPanel": ComponentSpec(
        a2ui_type="DetailPanel", native_type=ComponentType.DETAIL_PANEL,
        description="Animated expand/collapse container for item detail",
        optional_props=["sparkline", "metadata", "tabs"],
    ),
    "FilterBar": ComponentSpec(
        a2ui_type="FilterBar", native_type=ComponentType.FILTER_BAR,
        description="Horizontal category filter pill strip",
        required_props=["field", "values"], optional_props=["colors", "show_counts"],
    ),
}


def get_supported_components() -> list[dict[str, Any]]:
    """Get list of supported A2UI component types with specs."""
    return [{"type": s.a2ui_type, "nativeType": s.native_type.value,
             "description": s.description, "requiredProps": s.required_props,
             "optionalProps": s.optional_props,
             "supportsChildren": s.supports_children}
            for s in COMPONENT_CATALOG.values()]


def is_supported_type(a2ui_type: str) -> bool:
    """Check if an A2UI type is supported."""
    return a2ui_type in COMPONENT_CATALOG


def get_component_spec(a2ui_type: str) -> ComponentSpec | None:
    """Get spec for an A2UI component type."""
    return COMPONENT_CATALOG.get(a2ui_type)
