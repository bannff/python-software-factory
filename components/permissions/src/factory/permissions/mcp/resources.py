"""MCP Resource registration for permissions brick."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

from .docs import DOCS, list_docs
from .templates import PROMPT_TEMPLATES, list_templates

if TYPE_CHECKING:
    from factory.permissions.runtime.runtime import PermissionsRuntime


def register(mcp: Any, runtime: "PermissionsRuntime") -> None:
    """Register all permissions resources with the MCP server."""
    from factory.permissions.runtime.models import PolicyDefinition, Settings, Resource

    # Schema resources
    @mcp.resource("permissions://schemas/policy")
    def resource_policy_schema() -> str:
        """Get JSON schema for policy definitions."""
        return json.dumps(PolicyDefinition.model_json_schema(), indent=2)

    @mcp.resource("permissions://schemas/settings")
    def resource_settings_schema() -> str:
        """Get JSON schema for permissions settings."""
        return json.dumps(Settings.model_json_schema(), indent=2)

    @mcp.resource("permissions://schemas/resource")
    def resource_resource_schema() -> str:
        """Get JSON schema for resource objects."""
        return json.dumps(Resource.model_json_schema(), indent=2)

    # Documentation resources
    @mcp.resource("permissions://docs")
    def resource_docs_list() -> str:
        """List available permissions documentation."""
        docs = [{"name": k, "title": k.replace("-", " ").title()} for k in list_docs()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("permissions://docs/{doc_name}")
    def resource_doc(doc_name: str) -> str:
        """Get permissions documentation by name."""
        if doc_name in DOCS:
            return DOCS[doc_name]
        return f"Unknown doc: {doc_name}. Available: {list_docs()}"

    # Template resources
    @mcp.resource("permissions://templates")
    def resource_templates_list() -> str:
        """List available prompt templates."""
        templates = [
            {"name": k, "description": v.get("description", "")}
            for k, v in PROMPT_TEMPLATES.items()
        ]
        return json.dumps({"templates": templates}, indent=2)

    @mcp.resource("permissions://templates/{template_name}")
    def resource_template(template_name: str) -> str:
        """Get prompt template by name."""
        if template_name in PROMPT_TEMPLATES:
            return PROMPT_TEMPLATES[template_name]["template"]
        return f"Unknown template: {template_name}. Available: {list_templates()}"

    # Live data resources
    @mcp.resource("permissions://policies")
    def resource_policies() -> str:
        """List all loaded policy definitions."""
        policies = [
            {"id": p.id, "name": p.name, "version": p.version, "rules": len(p.rules)}
            for p in runtime.get_policies()
        ]
        return json.dumps({"policies": policies, "count": len(policies)}, indent=2)

    @mcp.resource("permissions://roles")
    def resource_roles() -> str:
        """List all registered roles."""
        roles = runtime.get_role_registry()
        return json.dumps({"roles": roles, "count": len(roles)}, indent=2)

    # Factory cross-reference
    @mcp.resource("permissions://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "related_bricks": {
                "auth": "Token validation and principal extraction",
                "workflow": "Permission-gated workflow steps",
                "events": "Permission change events",
            },
            "foreman_tools": ["foreman_info", "foreman_check"],
        }, indent=2)
