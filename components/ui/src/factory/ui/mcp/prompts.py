"""MCP Prompt registration for UI Module."""

from typing import Any
from .content import PROMPT_TEMPLATES

def register(mcp: Any):
    """Register all UI prompts with the MCP server."""

    @mcp.prompt()
    def create_dashboard(name: str, purpose: str, metrics: str = "", data: str = "") -> str:
        """Create a dashboard with metrics, charts, and tables."""
        return _fill_template("create_dashboard", {
            "name": name,
            "purpose": purpose,
            "metrics": metrics or "(not specified)",
            "data": data or "(not specified)",
        })

    @mcp.prompt()
    def add_visualization(view_id: str, data: str, title: str = "") -> str:
        """Add a data visualization to an existing view."""
        return _fill_template("add_visualization", {
            "view_id": view_id,
            "data": data,
            "title": title or "(auto-generate)",
        })

    @mcp.prompt()
    def design_form(purpose: str, fields: str) -> str:
        """Create a form for data collection."""
        return _fill_template("design_form", {
            "purpose": purpose,
            "fields": fields,
        })

def _fill_template(prompt_name: str, arguments: dict[str, Any]) -> str:
    """Fill a prompt template with arguments."""
    if prompt_name not in PROMPT_TEMPLATES:
        return f"Unknown prompt: {prompt_name}"
    
    template = PROMPT_TEMPLATES[prompt_name]["template"]
    for key, value in arguments.items():
        placeholder = "{" + key + "}"
        if isinstance(value, (list, dict)):
            import json
            value = json.dumps(value, indent=2)
        template = template.replace(placeholder, str(value))
    return template
