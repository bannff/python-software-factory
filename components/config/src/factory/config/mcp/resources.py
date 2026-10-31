"""MCP Resource registration for Config brick.

Resources expose static/queryable data:
- Schemas for configuration and feature flags
- Documentation on adapters and patterns
- Live configuration values (non-sensitive)
- Available configuration sources
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from typing import Any

from .docs import CONFIG_DOCS

if TYPE_CHECKING:
    from ..runtime.runtime import ConfigRuntime


def register(mcp: Any, get_runtime: Callable[[], "ConfigRuntime"]) -> None:
    """Register all Config resources with the MCP server."""
    from ..runtime.ports import ConfigHealth, ConfigValue

    # Schema resources
    @mcp.resource("config://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for configuration."""
        return json.dumps({
            "type": "object",
            "properties": {
                "backend": {
                    "type": "string",
                    "enum": ["env", "file", "ssm"],
                    "description": "Configuration backend type",
                },
                "prefix": {
                    "type": "string",
                    "description": "Key prefix for namespacing",
                },
                "path": {
                    "type": "string",
                    "description": "File path (for file backend)",
                },
                "region": {
                    "type": "string",
                    "description": "AWS region (for SSM backend)",
                },
            },
            "required": ["backend"],
        }, indent=2)

    @mcp.resource("config://schemas/feature-flag")
    def resource_feature_flag_schema() -> str:
        """Get the JSON schema for feature flags."""
        return json.dumps({
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Flag identifier"},
                "enabled": {"type": "boolean", "default": False},
                "description": {"type": "string"},
                "rollout_percentage": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                },
                "allowed_users": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "allowed_plans": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["name", "enabled"],
        }, indent=2)

    @mcp.resource("config://schemas/config-value")
    def resource_config_value_schema() -> str:
        """Get the JSON schema for ConfigValue."""
        return json.dumps({
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": ["string", "number", "boolean", "null"]},
                "source": {"type": "string"},
                "is_secret": {"type": "boolean"},
                "environment": {"type": ["string", "null"]},
            },
            "required": ["key", "value"],
        }, indent=2)

    # Documentation resources
    @mcp.resource("config://docs")
    def resource_docs_list() -> str:
        """List available config documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in CONFIG_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("config://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get config documentation by name."""
        if doc_name in CONFIG_DOCS:
            return CONFIG_DOCS[doc_name]["content"]
        available = list(CONFIG_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    # Live data resources
    @mcp.resource("config://values")
    def resource_values() -> str:
        """Get current configuration values (non-sensitive)."""
        runtime = get_runtime()
        config = runtime.get_config()
        keys = config.keys()
        # Filter out potentially sensitive keys
        sensitive_patterns = ["secret", "password", "token", "key", "credential"]
        safe_values = {}
        for key in keys:
            is_sensitive = any(p in key.lower() for p in sensitive_patterns)
            if is_sensitive:
                safe_values[key] = "[REDACTED]"
            else:
                safe_values[key] = config.get(key)
        return json.dumps({
            "environment": runtime.environment,
            "values": safe_values,
            "count": len(keys),
            "note": "Sensitive values are redacted",
        }, indent=2)

    @mcp.resource("config://sources")
    def resource_sources() -> str:
        """Get available configuration sources."""
        return json.dumps({
            "available_backends": ["env", "file", "ssm"],
            "backends": {
                "env": {
                    "description": "Environment variables",
                    "options": ["prefix"],
                    "example": "MYAPP_DATABASE_HOST",
                },
                "file": {
                    "description": "YAML/JSON file configuration",
                    "options": ["path"],
                    "formats": ["yaml", "json"],
                },
                "ssm": {
                    "description": "AWS Systems Manager Parameter Store",
                    "options": ["prefix", "region"],
                    "requires": "AWS credentials",
                },
            },
        }, indent=2)

    @mcp.resource("config://health")
    def resource_health() -> str:
        """Get health status of all active config stores."""
        runtime = get_runtime()
        health = runtime.health_check()
        return json.dumps({
            "environment": runtime.environment,
            "stores": {
                name: {
                    "healthy": h.healthy,
                    "backend": h.backend,
                    "latency_ms": h.latency_ms,
                    "message": h.message,
                }
                for name, h in health.items()
            },
            "all_healthy": all(h.healthy for h in health.values()) if health else True,
        }, indent=2)

    # Cross-reference to factory
    @mcp.resource("config://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": ["foreman_info", "foreman_check", "foreman_guardian_check"],
            "related_bricks": {
                "auth": "Uses config for auth settings",
                "workflow": "Uses config for workflow defaults",
                "events": "Uses config for event storage settings",
            },
        }, indent=2)

    # AWS identity resource
    @mcp.resource("config://aws/identity")
    def resource_aws_identity() -> str:
        """Get the active AWS identity (profile, region, account, ARN)."""
        runtime = get_runtime()
        identity = runtime.get_aws_identity()
        return json.dumps(identity.to_dict(), indent=2)
