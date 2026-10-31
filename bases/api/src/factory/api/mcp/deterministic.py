"""Deterministic MCP tools for API base."""

from __future__ import annotations

from typing import Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, ok

from ..runtime.runtime import APIRuntime
from .contracts.models import (
    CapabilitiesOutput,
    ConfigPropertyOutput,
    ConfigSchemaOutput,
    EmptyInput,
    HealthOutput,
    OpenAPISchemaOutput,
    RouteOutput,
    RoutesOutput,
)


def register(mcp: Any, get_runtime: Callable[[], APIRuntime]) -> None:
    """Register deterministic tools."""

    @mcp.tool(name="api_get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def api_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for API base."""
        return ok(CapabilitiesOutput(
            name="api", version="1.0.0", type="base",
            backends=APIRuntime.available_backends(),
            features=["rest_api", "graphql_api", "route_registration", "openapi_schema"],
        ))

    @mcp.tool(name="api_health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def api_health_check() -> ToolResult[HealthOutput]:
        """Fast readiness probe for API base."""
        return ok(HealthOutput(**get_runtime().health_check().to_dict()))

    @mcp.tool(name="api_describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def api_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe API configuration schema."""
        return ok(ConfigSchemaOutput(type="object", properties={
            "adapter": ConfigPropertyOutput(
                type="string", enum=["rest", "graphql"],
                description="API adapter type", default="rest",
            ),
            "title": ConfigPropertyOutput(
                type="string", description="API title for OpenAPI schema",
            ),
            "version": ConfigPropertyOutput(
                type="string", description="API version",
            ),
        }))

    @mcp.tool(name="api_list_routes")
    @deterministic(input_model=EmptyInput, output_model=RoutesOutput)
    def api_list_routes() -> ToolResult[RoutesOutput]:
        """List all registered API routes."""
        routes = [RouteOutput(**route.to_dict()) for route in get_runtime().list_routes()]
        return ok(RoutesOutput(routes=routes, count=len(routes)))

    @mcp.tool(name="api_get_openapi_schema")
    @deterministic(input_model=EmptyInput, output_model=OpenAPISchemaOutput)
    def api_get_openapi_schema() -> ToolResult[OpenAPISchemaOutput]:
        """Get OpenAPI schema for the API."""
        schema = get_runtime().get_openapi_schema()
        error = schema.get("error") if isinstance(schema, dict) else None
        if error:
            return ok(OpenAPISchemaOutput(
                status="unsupported", supported=False, error=error,
            ))
        return ok(OpenAPISchemaOutput(status="supported", supported=True, document=schema))
