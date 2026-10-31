"""Strict deterministic MCP tools for the Cache brick."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    CapabilitiesOutput,
    ConfigOptionOutput,
    DescribeConfigSchemaOutput,
    HealthOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import CacheRuntime


def register(mcp: Any, get_runtime: Callable[[], "CacheRuntime"]) -> None:
    """Register deterministic tools with strict Cache-local contracts."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for cache brick."""
        from ..runtime.runtime import CacheRuntime

        EmptyInput.model_validate({})
        return ok(CapabilitiesOutput(
            name="cache", version="1.0.0", backends=CacheRuntime.available_backends(),
            features=["key_value", "ttl_support", "pattern_matching", "stats"],
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Fast readiness probe for cache brick."""
        EmptyInput.model_validate({})
        health = get_runtime().health_check()
        return ok(HealthOutput(
            healthy=all(item.healthy for item in health.values()) if health else True,
            caches={name: {"healthy": item.healthy, "backend": item.backend} for name, item in health.items()},
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=DescribeConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[DescribeConfigSchemaOutput]:
        """Describe cache configuration schema."""
        EmptyInput.model_validate({})
        return ok(DescribeConfigSchemaOutput(type="object", properties={
            "backend": ConfigOptionOutput(
                type="string", enum=["memory", "redis"], description="Cache backend type",
            ),
            "url": ConfigOptionOutput(type="string", description="Redis URL (for redis backend)"),
            "max_size": ConfigOptionOutput(type="integer", description="Max entries (for memory backend)"),
            "prefix": ConfigOptionOutput(type="string", description="Key prefix (for redis backend)"),
        }))
