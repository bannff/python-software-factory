"""Deterministic typed MCP tools for the HTTP brick."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import (
    BackendsOutput, BackendOutput, CapabilitiesFeaturesOutput, CapabilitiesOutput,
    ConfigGroupOutput, ConfigSchemaOutput, EmptyInput, HealthOutput, ClientHealthOutput,
    SchemaPropertyOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import HTTPRuntime


def register(mcp: Any, get_runtime: Callable[[], "HTTPRuntime"]) -> None:
    """Register read-only HTTP tools with wire-preserving validation."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def http_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get HTTP module capabilities and status."""
        EmptyInput.model_validate({})
        from ..runtime.runtime import HTTPRuntime
        return ok(CapabilitiesOutput(name="http", version="1.0.0",
            backends=HTTPRuntime.available_backends(), features=CapabilitiesFeaturesOutput(
                retry_logic=True, rate_limiting=True, auth_headers=True,
                timeout_handling=True, async_support=True)))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def http_health_check() -> ToolResult[HealthOutput]:
        """Check health of the HTTP module."""
        EmptyInput.model_validate({})
        try:
            health = get_runtime().health_check()
        except Exception:
            return ok(HealthOutput(status="unhealthy", clients={}, error="health_check_failed"))
        clients = {name: ClientHealthOutput(healthy=item.healthy, backend=item.backend)
                   for name, item in health.items()}
        status = "healthy" if all(item.healthy for item in health.values()) else "degraded"
        return ok(HealthOutput(status=status, clients=clients))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def http_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Get JSON schema for HTTP configuration."""
        EmptyInput.model_validate({})
        prop = SchemaPropertyOutput
        return ok(ConfigSchemaOutput(
            client_config=ConfigGroupOutput(type="object", properties={
                "backend": prop(type="string", enum=["httpx", "aiohttp"], description="HTTP backend to use"),
                "base_url": prop(type="string", description="Base URL for requests"),
                "timeout": prop(type="number", description="Default timeout in seconds")}),
            retry_config=ConfigGroupOutput(type="object", properties={
                "max_retries": prop(type="integer", default=3),
                "backoff_factor": prop(type="number", default=0.5),
                "retry_statuses": prop(type="array", default=[429, 500, 502, 503, 504])}),
            rate_limit_config=ConfigGroupOutput(type="object", properties={
                "requests_per_second": prop(type="number", default=10.0),
                "burst_size": prop(type="integer", default=20)}),
            auth_config=ConfigGroupOutput(type="object", properties={
                "auth_type": prop(type="string", enum=["none", "bearer", "basic", "api_key"]),
                "token": prop(type="string"), "username": prop(type="string"),
                "password": prop(type="string"), "api_key_header": prop(type="string", default="X-API-Key"),
                "api_key_value": prop(type="string")})))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=BackendsOutput)
    def http_list_backends() -> ToolResult[BackendsOutput]:
        """List available HTTP backends with their features."""
        EmptyInput.model_validate({})
        from ..runtime.runtime import HTTPRuntime
        return ok(BackendsOutput(backends=[
            BackendOutput(name="httpx", description="Modern HTTP client with HTTP/2 support",
                features=["http2", "sync", "async", "connection_pooling"], recommended_for=["general_use", "api_clients"]),
            BackendOutput(name="aiohttp", description="Async HTTP client for high concurrency",
                features=["async", "websockets", "streaming"], recommended_for=["high_concurrency", "websockets"])],
            default="httpx", available=HTTPRuntime.available_backends()))
