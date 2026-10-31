"""Strict typed deterministic MCP tools for Notification."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts.inputs import EmptyInput
from .contracts.outputs import (
    CapabilitiesOutput, ChannelRegistryOutput, ConfigSchemaOutput, HealthOutput,
    RegistryItemOutput, TemplateRegistryOutput,
)

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register deterministic tools with strict flat ingress and typed egress."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get module capabilities without exposing configuration paths."""
        EmptyInput.model_validate({})
        data = runtime.get_capabilities()
        return ok(CapabilitiesOutput(
            module=data["module"], version=data["version"],
            deterministic_tools=data["deterministic_tools"],
            operational_tools=data["operational_tools"],
            authoring={"env_var": data["authoring"]["env_var"]},
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Return the sync-safe configuration health summary."""
        EmptyInput.model_validate({})
        return ok(HealthOutput(
            ok=True, backend=runtime.backend.name if runtime.backend else "none",
            channels_loaded=len(runtime.channels.channels) if runtime.channels else 0,
            templates_loaded=len(runtime.templates.templates) if runtime.templates else 0,
        ))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ChannelRegistryOutput)
    def get_channel_registry() -> ToolResult[ChannelRegistryOutput]:
        """List sanitized configured notification channels."""
        EmptyInput.model_validate({})
        items = [RegistryItemOutput.model_validate(item) for item in runtime.get_channel_registry()]
        return ok(ChannelRegistryOutput(channels=items, count=len(items)))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=TemplateRegistryOutput)
    def get_template_registry() -> ToolResult[TemplateRegistryOutput]:
        """List configured notification templates."""
        EmptyInput.model_validate({})
        items = [RegistryItemOutput.model_validate(item) for item in runtime.get_template_registry()]
        return ok(TemplateRegistryOutput(templates=items, count=len(items)))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Get JSON schemas for all configuration types."""
        EmptyInput.model_validate({})
        return ok(ConfigSchemaOutput.model_validate(runtime.describe_config_schema()))
