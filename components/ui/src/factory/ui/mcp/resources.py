"""MCP Resource registration for UI Module."""

import json
from typing import Any, TYPE_CHECKING
from .content import VIEW_TEMPLATES, UI_DOCS, COMPONENT_EXAMPLES

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime

def register(mcp: Any, get_runtime: Any):
    """Register all UI resources with the MCP server."""

    @mcp.resource("ui://components")
    def resource_all_components() -> str:
        """List all available UI component types with their schemas."""
        runtime = get_runtime()
        assert runtime.view_manager is not None
        registry = runtime.view_manager.registry
        components = []
        for defn in registry.list_components():
            components.append({
                "type": defn.component_type.value,
                "name": defn.name,
                "description": defn.description,
                "schema": defn.schema,
            })
        return json.dumps({"components": components, "total": len(components)}, indent=2)

    @mcp.resource("ui://components/{component_type}")
    def resource_component_schema(component_type: str) -> str:
        """Get the JSON schema for a specific component type."""
        runtime = get_runtime()
        assert runtime.view_manager is not None
        registry = runtime.view_manager.registry
        from ..runtime.models import ComponentType
        try:
            comp_type = ComponentType(component_type)
            definition = registry.get(comp_type)
            if definition:
                return json.dumps({
                    "type": component_type,
                    "name": definition.name,
                    "description": definition.description,
                    "schema": definition.schema,
                    "default_props": definition.default_props,
                    "default_styles": definition.default_styles,
                    "example": COMPONENT_EXAMPLES.get(component_type, {}),
                }, indent=2)
        except ValueError:
            pass
        return json.dumps({"error": f"Unknown component type: {component_type}"})

    @mcp.resource("ui://templates")
    def resource_all_templates() -> str:
        """List all available view templates."""
        return json.dumps({
            "templates": list(VIEW_TEMPLATES.keys()),
            "details": {k: {"name": v["name"], "description": v["description"]} for k, v in VIEW_TEMPLATES.items()}
        }, indent=2)

    @mcp.resource("ui://templates/{template_name}")
    def resource_template(template_name: str) -> str:
        """Get a specific view template."""
        if template_name in VIEW_TEMPLATES:
            return json.dumps(VIEW_TEMPLATES[template_name], indent=2)
        return json.dumps({"error": f"Unknown template: {template_name}"})

    @mcp.resource("ui://views/{view_id}")
    def resource_view(view_id: str) -> str:
        """Get a specific view's current state."""
        runtime = get_runtime()
        view = runtime.view_manager.get_view(view_id)
        if view:
            return json.dumps(view.to_dict(), indent=2)
        return json.dumps({"error": f"View not found: {view_id}"})

    @mcp.resource("ui://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get documentation content."""
        if doc_name in UI_DOCS:
            return UI_DOCS[doc_name]["content"]
        return f"Documentation not found: {doc_name}"
