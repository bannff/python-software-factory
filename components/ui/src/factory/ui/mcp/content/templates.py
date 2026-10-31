"""View templates for UI MCP module."""

VIEW_TEMPLATES = {
    "dashboard": {
        "name": "Dashboard Template",
        "description": "A standard dashboard with metrics, charts, and tables",
        "layout": {"type": "grid", "columns": 3},
        "suggested_components": [
            {"type": "metric", "count": "3-6", "purpose": "KPIs at the top"},
            {"type": "chart", "count": "1-3", "purpose": "Data visualizations"},
            {"type": "table", "count": "0-2", "purpose": "Detailed data"},
        ],
        "example": {
            "name": "Sales Dashboard",
            "metrics": [
                {"label": "Revenue", "value": "$50K"},
                {"label": "Orders", "value": "1,234"},
                {"label": "Customers", "value": "567"},
            ],
            "charts": [{"title": "Monthly Trend", "chart_type": "line"}],
        },
    },
    "report": {
        "name": "Report Template",
        "description": "A report layout with title, summary, and detailed sections",
        "layout": {"type": "flex", "direction": "column"},
        "suggested_components": [
            {"type": "text", "variant": "h1", "purpose": "Report title"},
            {"type": "text", "variant": "body", "purpose": "Executive summary"},
            {"type": "chart", "count": "1-2", "purpose": "Key visualizations"},
            {"type": "table", "count": "1-3", "purpose": "Detailed data tables"},
        ],
    },
    "form": {
        "name": "Form Template",
        "description": "A form layout for data collection",
        "layout": {"type": "flex", "direction": "column"},
        "suggested_components": [
            {"type": "text", "variant": "h2", "purpose": "Form title"},
            {"type": "form", "count": 1, "purpose": "Input fields"},
            {"type": "alert", "purpose": "Validation messages"},
        ],
    },
    "status": {
        "name": "Status Page Template",
        "description": "A status/health page showing system state",
        "layout": {"type": "grid", "columns": 2},
        "suggested_components": [
            {"type": "text", "variant": "h1", "purpose": "Page title"},
            {"type": "alert", "count": "1-3", "purpose": "Status indicators"},
            {"type": "metric", "count": "2-6", "purpose": "Health metrics"},
            {"type": "progress", "count": "0-4", "purpose": "Resource usage"},
        ],
    },
}
