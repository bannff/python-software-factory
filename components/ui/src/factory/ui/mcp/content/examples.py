"""Component examples for UI MCP module."""

COMPONENT_EXAMPLES = {
    "text": {
        "props": {"content": "Hello, World!", "variant": "h1"},
        "description": "Display a heading",
    },
    "metric": {
        "props": {"label": "Revenue", "value": "$50,000", "trend": "up", "trend_value": "+12%"},
        "description": "Display a KPI with trend indicator",
    },
    "chart": {
        "props": {
            "chart_type": "line",
            "title": "Monthly Sales",
            "data": [{"month": "Jan", "value": 100}, {"month": "Feb", "value": 150}],
        },
        "description": "Display a line chart",
    },
    "table": {
        "props": {
            "columns": [{"key": "name", "label": "Name"}, {"key": "value", "label": "Value"}],
            "rows": [{"name": "Item 1", "value": 100}, {"name": "Item 2", "value": 200}],
        },
        "description": "Display tabular data",
    },
    "alert": {
        "props": {"message": "Operation successful!", "severity": "success"},
        "description": "Display a success alert",
    },
    "progress": {
        "props": {"value": 75, "label": "Loading..."},
        "description": "Display a progress bar",
    },
    "card": {
        "props": {"title": "Card Title", "subtitle": "Subtitle", "content": "Card content here"},
        "description": "Display a card container",
    },
    "form": {
        "props": {
            "fields": [
                {"name": "email", "type": "email", "label": "Email"},
                {"name": "message", "type": "textarea", "label": "Message"},
            ],
            "submit_label": "Send",
        },
        "description": "Display a form",
    },
}
