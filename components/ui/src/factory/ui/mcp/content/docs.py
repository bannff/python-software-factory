"""Documentation content for UI MCP module."""

UI_DOCS = {
    "getting-started": {
        "name": "Getting Started",
        "description": "Quick start guide for using the UI module",
        "content": """# Getting Started with UI Module

## Overview

The UI Module lets you create and update user interfaces through conversation.
Instead of writing code, you describe what you want and the agent builds it.

## Basic Workflow

1. **Create a view**: `ui_create_view(name="My Dashboard")`
2. **Add components**: `ui_add_component(view_id, component_type="metric", props={...})`
3. **Update as needed**: `ui_update_component(view_id, component_id, props={...})`

## Available Components

- `text` - Headings and paragraphs
- `metric` - KPI cards with trends
- `chart` - Line, bar, pie charts
- `table` - Data tables
- `alert` - Notifications
- `progress` - Progress bars
- `form` - Input forms
- `card` - Container cards

## Tips

- Use `ui://components` resource to see all component schemas
- Use `ui://templates/dashboard` for dashboard patterns
- Always provide meaningful labels and titles
""",
    },
    "component-guide": {
        "name": "Component Guide",
        "description": "Detailed guide for each component type",
        "content": """# Component Guide

## Metric Component

Best for: KPIs, statistics, single values with context

```json
{
  "type": "metric",
  "props": {
    "label": "Revenue",
    "value": "$50,000",
    "unit": "USD",
    "trend": "up",
    "trend_value": "+12%"
  }
}
```

## Chart Component

Best for: Trends, comparisons, distributions

```json
{
  "type": "chart",
  "props": {
    "chart_type": "line",  // line, bar, pie, area
    "title": "Monthly Sales",
    "data": [{"x": "Jan", "y": 100}, {"x": "Feb", "y": 150}]
  }
}
```

## Table Component

Best for: Detailed data, lists, records

```json
{
  "type": "table",
  "props": {
    "columns": [
      {"key": "name", "label": "Name"},
      {"key": "value", "label": "Value"}
    ],
    "rows": [
      {"name": "Item 1", "value": 100}
    ],
    "sortable": true
  }
}
```
""",
    },
    "best-practices": {
        "name": "Best Practices",
        "description": "UI design patterns and recommendations",
        "content": """# UI Best Practices

## Dashboard Design

1. **Lead with KPIs**: Put metrics at the top
2. **3-6 metrics max**: Don't overwhelm users
3. **Use grid layout**: 3 columns works well
4. **Charts below metrics**: For detailed trends
5. **Tables at bottom**: For drill-down data

## Layout Tips

- **Grid**: Best for dashboards, equal-sized items
- **Flex column**: Best for reports, sequential content
- **Flex row**: Best for side-by-side comparisons
""",
    },
}
