"""MCP Resource registration for Test brick.

Resources expose static/queryable data:
- Schemas for test configuration and typed tool results
- Documentation on testing patterns
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable, Union

from typing import Any
from factory.mcp_utils.interface import ToolResult

from .contracts import (
    AuthoringStatusOutput,
    CapabilitiesOutput,
    ConfigSchemaOutput,
    DiscoveryOutput,
    ExecutionOutput,
    HealthOutput,
    JunitCompareOutput,
    ListFilesOutput,
    MutationOutput,
)
from .docs import TEST_DOCS

if TYPE_CHECKING:
    from pathlib import Path
    from ..runtime.runtime import TestRuntime


_SAFE_ADAPTERS = {"pytest", "memory"}
_RESULT_DATA = Union[
    CapabilitiesOutput,
    HealthOutput,
    ConfigSchemaOutput,
    DiscoveryOutput,
    JunitCompareOutput,
    ExecutionOutput,
    ListFilesOutput,
    AuthoringStatusOutput,
    MutationOutput,
]


def _safe_runtime_info(runtime: "TestRuntime") -> dict[str, object]:
    """Return only stable, non-path runtime fields for the public resource."""
    adapter = str(getattr(runtime, "adapter_type", "unknown"))
    adapter = adapter if adapter in _SAFE_ADAPTERS else "unknown"
    try:
        health = runtime.health_check()
    except Exception:
        health = {}
    status = str(health.get("status", "unknown"))
    status = status if status in {"healthy", "unhealthy"} else "unknown"
    backend = str(health.get("backend", "unknown"))
    backend = backend if backend in _SAFE_ADAPTERS else "unknown"
    version = str(health.get("version", "unknown"))
    version = version if version and len(version) <= 64 and all(
        char.isalnum() or char in ".-_+" for char in version
    ) else "unknown"
    return {
        "root_dir": "<test-root>", "adapter_type": adapter,
        "adapter_health": {"status": status, "backend": backend, "version": version},
    }


def register(
    mcp: Any,
    get_runtime: Callable[[], "TestRuntime"],
    get_config_dir: Callable[[], "Path"],
) -> None:
    """Register all Test resources with the MCP server."""

    @mcp.resource("test://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for test configuration."""
        schema = {
            "type": "object",
            "properties": {
                "root_dir": {"type": "string", "default": "."},
                "adapter": {"type": "string", "enum": ["pytest", "memory"], "default": "pytest"},
                "default_pattern": {"type": "string", "default": "test_*.py"},
                "timeout": {"type": "integer", "default": 300},
                "verbose": {"type": "boolean", "default": False},
            },
            "required": [],
            "additionalProperties": False,
        }
        return json.dumps(schema, indent=2)

    @mcp.resource("test://schemas/result")
    def resource_result_schema() -> str:
        """Get the complete union schema for every typed Test tool result."""
        schema = ToolResult[_RESULT_DATA].model_json_schema()
        schema["$id"] = "test://schemas/result"
        schema["description"] = (
            "v1 ToolResult envelope; data is one of the nine public Test output DTOs. "
            "DTOs enforce field bounds and reject extra fields; projections enforce "
            "output-size, redaction, and path-identity limits before serialization."
        )
        return json.dumps(schema, indent=2)

    @mcp.resource("test://docs")
    def resource_docs_list() -> str:
        """List available test documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in TEST_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("test://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get test documentation by name."""
        if doc_name in TEST_DOCS:
            return TEST_DOCS[doc_name]["content"]
        available = list(TEST_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    @mcp.resource("test://info")
    def resource_info() -> str:
        """Get safe, allowlisted test runtime information."""
        return json.dumps(_safe_runtime_info(get_runtime()), indent=2)

    @mcp.resource("test://adapters")
    def resource_adapters() -> str:
        """List available test adapters."""
        adapters = {
            "adapters": [
                {"name": "pytest", "description": "Real pytest execution via subprocess", "default": True},
                {"name": "memory", "description": "In-memory mock for testing", "default": False},
            ],
        }
        return json.dumps(adapters, indent=2)

    @mcp.resource("test://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": ["foreman_info", "foreman_check", "foreman_guardian_check"],
            "related_bricks": {
                "workflow": "Can trigger test runs as workflow steps",
                "events": "Publishes test.completed events",
            },
        }, indent=2)
