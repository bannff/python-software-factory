"""JSON Schema definitions for UI configuration."""

from typing import Any


def get_config_schema() -> dict[str, Any]:
    """Get JSON schema for UI configuration."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "UI Module Configuration",
        "type": "object",
        "properties": {
            "settings": {
                "type": "object",
                "properties": {
                    "authoring_enabled": {"type": "boolean", "default": False},
                    "push_enabled": {"type": "boolean", "default": True},
                    "max_clients": {"type": "integer", "default": 100},
                    "storage_backend": {"type": "string", "enum": ["memory", "redis", "filesystem"]},
                    "storage_path": {"type": "string"},
                    "default_adapter": {"type": "string", "default": "json"},
                    "enabled_adapters": {"type": "array", "items": {"type": "string"}},
                    "max_views": {"type": "integer", "default": 1000},
                    "max_components_per_view": {"type": "integer", "default": 100},
                    "max_history_entries": {"type": "integer", "default": 1000},
                    "feature_flags": {"type": "object", "additionalProperties": {"type": "boolean"}},
                },
            },
            "view_definition": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "layout": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["flex", "grid"]},
                            "columns": {"type": "integer"},
                            "direction": {"type": "string"},
                        },
                    },
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "props": {"type": "object"},
                                "styles": {"type": "object"},
                            },
                        },
                    },
                    "metadata": {"type": "object"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }
