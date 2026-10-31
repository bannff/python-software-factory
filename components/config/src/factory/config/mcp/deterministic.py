"""Deterministic Config MCP tools with strict local DTO boundaries."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    AwsIdentityInput,
    AwsIdentityOutput,
    CapabilitiesOutput,
    ConfigHealthOutput,
    ConfigSchemaOutput,
    EmptyInput,
    EnvironmentOutput,
    HealthCheckOutput,
    SchemaPropertyOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import ConfigRuntime


def register(mcp: Any, get_runtime: Callable[[], "ConfigRuntime"]) -> None:
    """Register deterministic tools while preserving flat public kwargs."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable Config brick capabilities."""
        from ..runtime.runtime import ConfigRuntime

        return ok(CapabilitiesOutput(
            name="config", version="1.0.0", backends=ConfigRuntime.available_backends(),
            features=["key_value", "typed_values", "layered_config", "feature_flags", "aws_identity"],
            mcp_resources=["config://schemas/config", "config://schemas/feature-flag", "config://docs", "config://values", "config://sources"],
            mcp_prompts=["configure_source", "add_feature_flag", "debug_config", "migrate_config"],
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthCheckOutput)
    def health_check() -> ToolResult[HealthCheckOutput]:
        """Return Config readiness without changing no-config semantics."""
        runtime = get_runtime()
        health = runtime.health_check()
        if not health:
            return ok(HealthCheckOutput(
                healthy=True, environment=runtime.environment, configs={},
                message="No configs initialized",
            ))
        return ok(HealthCheckOutput(
            healthy=all(item.healthy for item in health.values()),
            environment=runtime.environment,
            configs={name: ConfigHealthOutput(healthy=item.healthy, backend=item.backend)
                     for name, item in health.items()},
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe the Config backend setup schema."""
        return ok(ConfigSchemaOutput(
            type="object",
            properties={
                "backend": SchemaPropertyOutput(type="string", enum=["env", "file", "ssm"], description="Configuration backend type"),
                "prefix": SchemaPropertyOutput(type="string", description="Key prefix for namespacing"),
                "path": SchemaPropertyOutput(type="string", description="File path (for file backend)"),
                "region": SchemaPropertyOutput(type="string", description="AWS region (for SSM backend)"),
            },
            required=["backend"],
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=EnvironmentOutput)
    def config_environment() -> ToolResult[EnvironmentOutput]:
        """Get the current environment."""
        return ok(EnvironmentOutput(environment=get_runtime().environment))

    @typed_tool(mcp)
    @deterministic(input_model=AwsIdentityInput, output_model=AwsIdentityOutput)
    def config_get_aws_identity(force_refresh: bool = False) -> ToolResult[AwsIdentityOutput]:
        """Get the cached or refreshed active AWS identity."""
        return ok(AwsIdentityOutput(**get_runtime().get_aws_identity(force=force_refresh).to_dict()))
