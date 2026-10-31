"""Prompt templates for UI MCP module."""

PROMPT_TEMPLATES = {
    "create_dashboard": {
        "description": "Create a dashboard with metrics, charts, and tables",
        "arguments": [
            {"name": "name", "description": "Dashboard name", "required": True},
            {"name": "purpose", "description": "What the dashboard is for", "required": True},
            {"name": "metrics", "description": "List of KPIs to display", "required": False},
            {"name": "data", "description": "Data to visualize", "required": False},
        ],
        "template": """Create a dashboard with the following requirements:

**Name**: {name}
**Purpose**: {purpose}

**Metrics to display**:
{metrics}

**Data to visualize**:
{data}

## Instructions

1. First, read the `ui://templates/dashboard` resource to understand the recommended layout
2. Read `ui://components` to see available component types and their schemas
3. Use `ui_create_view` to create the dashboard with a grid layout (3 columns)
4. Add metric components at the top for KPIs
5. Add chart components for data visualization
6. Add table components if detailed data is needed
""",
    },
    "add_visualization": {
        "description": "Add a data visualization to an existing view",
        "arguments": [
            {"name": "view_id", "description": "Target view ID", "required": True},
            {"name": "data", "description": "Data to visualize", "required": True},
            {"name": "title", "description": "Chart title", "required": False},
        ],
        "template": """Add a visualization to view `{view_id}` for this data:

```json
{data}
```

**Title**: {title}

## Instructions

1. Analyze the data structure to determine the best chart type:
   - Time series data (dates/timestamps) → line chart
   - Category comparisons → bar chart
   - Part-to-whole relationships → pie chart (max 5-6 slices)
   - Correlation between variables → scatter chart
   - Cumulative values → area chart

2. Read `ui://components/chart` for the chart component schema

3. Use `ui_add_component` with:
   - `component_type`: "chart"
   - `props.chart_type`: chosen type
   - `props.title`: descriptive title
   - `props.data`: formatted data array
""",
    },
    "design_form": {
        "description": "Create a form for data collection",
        "arguments": [
            {"name": "purpose", "description": "What the form collects", "required": True},
            {"name": "fields", "description": "Fields to include", "required": True},
        ],
        "template": """Create a form for: {purpose}

**Fields needed**:
{fields}

## Instructions

1. Read `ui://templates/form` for the recommended form layout
2. Read `ui://components/form` for the form component schema

3. Create a view with flex column layout:
   ```
   ui_create_view(name="...", layout_type="flex")
   ```

4. Add a title using text component with variant "h2"
""",
    },
}
