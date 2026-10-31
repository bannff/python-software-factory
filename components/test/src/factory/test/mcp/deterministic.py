"""Deterministic MCP tools for the strict Test boundary."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import (
    CapabilitiesFeatures, CapabilitiesOutput, ConfigSchemaOutput, DiscoveryInput,
    DiscoveryOutput, EmptyInput, HealthOutput, JunitCompareInput, JunitCompareOutput,
    supplied_input_fields,
)
from ..runtime.mcp_containment import ContainmentError, McpTestRuntime

if TYPE_CHECKING:
    from pathlib import Path
    from ..runtime.runtime import TestRuntime


_SAFE_ADAPTERS = {"pytest", "memory"}


def _safe_adapter(value: object) -> str:
    text = str(value)
    return text if text in _SAFE_ADAPTERS else "unknown"


def _safe_version(value: object) -> str:
    text = str(value)
    return text if text and len(text) <= 64 and all(
        char.isalnum() or char in ".-_+" for char in text
    ) else "unknown"


def register(mcp: Any, get_runtime: Callable[[], "TestRuntime"],
             get_config_dir: Callable[[], "Path"]) -> None:
    """Register read-only Test tools."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def test_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get Test-brick capabilities and current adapter."""
        runtime = get_runtime()
        return ok(CapabilitiesOutput(
            name="test", version="0.1.0",
            description="Trusted-local test execution and discovery",
            config_dir="<configured>", adapter=_safe_adapter(runtime.adapter_type),
            features=CapabilitiesFeatures(
                run_all_tests=True, run_component_tests=True, test_discovery=True,
                junit_debt_comparison=True, adapters=["pytest", "memory"],
            ),
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def test_health_check() -> ToolResult[HealthOutput]:
        """Check whether the configured Test adapter is available."""
        config_dir = "<configured>"
        try:
            health = get_runtime().health_check()
        except Exception:
            return ok(HealthOutput(status="unhealthy", config_dir=config_dir,
                                   error="health_check_failed"))
        status = str(health.get("status", "unknown"))
        status = status if status in {"healthy", "unhealthy"} else "unknown"
        return ok(HealthOutput(
            status=status,
            backend=_safe_adapter(health.get("backend", "unknown")),
            version=_safe_version(health.get("version", "unknown")),
            config_dir=config_dir,
            error="adapter_unhealthy" if status == "unhealthy" else None,
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def test_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Return the Test-brick configuration schema."""
        return ok(ConfigSchemaOutput(schema_definition={
            "type": "object", "properties": {
                "root_dir": {"type": "string", "default": "."},
                "adapter": {"type": "string", "enum": ["pytest", "memory"], "default": "pytest"},
                "default_pattern": {"type": "string", "default": "test_*.py"},
                "timeout": {"type": "integer", "default": 300},
                "verbose": {"type": "boolean", "default": False},
            }, "required": [], "additionalProperties": False,
        }))

    @typed_tool(mcp)
    @deterministic(input_model=DiscoveryInput, output_model=DiscoveryOutput)
    def test_discover(path: str = ".", pattern: str = "test_*.py") -> ToolResult[DiscoveryOutput]:
        """Discover tests under a contained workspace-relative path."""
        facade = McpTestRuntime(get_runtime())
        try:
            return ok(DiscoveryOutput(**facade.discover(
                path, pattern, pattern_supplied="pattern" in supplied_input_fields()
            )))
        except ContainmentError as exc:
            return ok(DiscoveryOutput(**facade.rejected_discovery(exc.code)))

    @typed_tool(mcp)
    @deterministic(input_model=JunitCompareInput, output_model=JunitCompareOutput)
    def test_compare_junit(base_report: str, candidate_report: str) -> ToolResult[JunitCompareOutput]:
        """Compare contained JUnit reports while preserving the domain result shape."""
        facade = McpTestRuntime(get_runtime())
        try:
            return ok(JunitCompareOutput(**facade.compare_junit(base_report, candidate_report)))
        except ContainmentError as exc:
            return ok(JunitCompareOutput(**facade.rejected_junit(exc.code)))
