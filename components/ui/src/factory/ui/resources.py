"""Pure-Python resource helpers for the UI module.

These mirror the MCP resource payloads but are usable directly by tests
without requiring an MCP server instance.
"""

from __future__ import annotations

import json
from typing import Any

from .runtime import ComponentRegistry, ViewManager
from .runtime.models import ComponentType
from .mcp.content import COMPONENT_EXAMPLES, UI_DOCS, VIEW_TEMPLATES


def get_all_components_resource(registry: ComponentRegistry) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for defn in registry.list_components():
        components.append(
            {
                "type": defn.component_type.value,
                "name": defn.name,
                "description": defn.description,
                "schema": defn.schema,
            }
        )

    return {
        "uri": "ui://components",
        "mimeType": "application/json",
        "content": json.dumps({"components": components, "total": len(components)}),
    }


def get_component_schema_resource(component_type: str, registry: ComponentRegistry) -> dict[str, Any]:
    try:
        comp_type = ComponentType(component_type)
    except ValueError:
        return {
            "uri": f"ui://components/{component_type}",
            "mimeType": "application/json",
            "content": json.dumps({"error": f"Unknown component type: {component_type}"}),
        }

    definition = registry.get(comp_type)
    if not definition:
        return {
            "uri": f"ui://components/{component_type}",
            "mimeType": "application/json",
            "content": json.dumps({"error": f"Unknown component type: {component_type}"}),
        }

    return {
        "uri": f"ui://components/{component_type}",
        "mimeType": "application/json",
        "content": json.dumps(
            {
                "type": component_type,
                "name": definition.name,
                "description": definition.description,
                "schema": definition.schema,
                "default_props": definition.default_props,
                "default_styles": definition.default_styles,
                "example": COMPONENT_EXAMPLES.get(component_type, {}),
            }
        ),
    }


def get_all_templates_resource() -> dict[str, Any]:
    return {
        "uri": "ui://templates",
        "mimeType": "application/json",
        "content": json.dumps({"templates": list(VIEW_TEMPLATES.keys())}),
    }


def get_template_resource(template_name: str) -> dict[str, Any]:
    payload: dict[str, Any]
    if template_name in VIEW_TEMPLATES:
        payload = VIEW_TEMPLATES[template_name]
    else:
        payload = {"error": f"Unknown template: {template_name}"}

    return {
        "uri": f"ui://templates/{template_name}",
        "mimeType": "application/json",
        "content": json.dumps(payload),
    }


def get_view_resource(view_id: str, manager: ViewManager) -> dict[str, Any]:
    view = manager.get_view(view_id)
    if not view:
        payload: dict[str, Any] = {"error": f"View not found: {view_id}"}
    else:
        payload = view.to_dict()

    return {
        "uri": f"ui://views/{view_id}",
        "mimeType": "application/json",
        "content": json.dumps(payload),
    }


def get_docs_resource(doc_name: str) -> dict[str, Any]:
    if doc_name in UI_DOCS:
        content = UI_DOCS[doc_name]["content"]
    else:
        content = f"Documentation not found: {doc_name}"

    return {
        "uri": f"ui://docs/{doc_name}",
        "mimeType": "text/markdown",
        "content": content,
    }


def list_all_resources(registry: ComponentRegistry, manager: ViewManager) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []

    resources.append(get_all_components_resource(registry))
    resources.append(get_all_templates_resource())

    for view in manager.list_views():
        resources.append(get_view_resource(view.id, manager))

    for doc_name in UI_DOCS.keys():
        resources.append(get_docs_resource(doc_name))

    return resources
