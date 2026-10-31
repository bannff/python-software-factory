"""Deterministic MCP tools for the UI module."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .typed_dtos import (
    AdaptersOutput,
    CapabilitiesOutput,
    ComponentRegistryOutput,
    ConfigSchemaOutput,
    EmptyInput,
    HealthOutput,
    ThemeInfoInput,
    ThemeInfoOutput,
    ViewRegistryOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register deterministic UI tools."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def ui_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Get module capabilities."""
        return CapabilitiesOutput(**get_runtime().get_capabilities())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def ui_health_check() -> ToolResult[HealthOutput]:
        """Check service health."""
        return HealthOutput(**get_runtime().health_check())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def ui_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Get JSON schema for configuration."""
        return ConfigSchemaOutput(**get_runtime().describe_config_schema())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewRegistryOutput)
    def ui_get_view_registry() -> ToolResult[ViewRegistryOutput]:
        """Get sanitized list of loaded views."""
        return ViewRegistryOutput(**get_runtime().get_view_registry())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ComponentRegistryOutput)
    def ui_get_component_registry() -> ToolResult[ComponentRegistryOutput]:
        """Get available component types and their schemas."""
        runtime = get_runtime()
        result = runtime.view_manager.registry.to_dict() if runtime.view_manager else {"components": []}
        return ComponentRegistryOutput(**result)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=AdaptersOutput)
    def ui_list_adapters() -> ToolResult[AdaptersOutput]:
        """List available render adapters with their capabilities."""
        runtime = get_runtime()
        if runtime.view_manager:
            return AdaptersOutput(
                adapters=runtime.view_manager.list_adapters(),
                default=runtime.settings.default_adapter if runtime.settings else "json",
                recommendations={"agent_facing": "htmx", "user_facing": "react", "api": "json", "inline_html": "inline-html", "mixed": "hybrid"},
            )
        return AdaptersOutput(adapters=[], default="json")

    @mcp.tool()
    @deterministic(input_model=ThemeInfoInput, output_model=ThemeInfoOutput)
    def ui_get_theme_info(framework: str = "all") -> ToolResult[ThemeInfoOutput]:
        """Get available themes for ``daisyui``, ``shadcn``, or ``all``."""
        from ..runtime.themes import DAISY_THEMES, SHADCN_THEMES

        result = {}
        if framework in ("all", "daisyui"):
            result["daisyui"] = {"themes": DAISY_THEMES, "adapter": "htmx", "description": "DaisyUI themes for server-rendered HTML"}
        if framework in ("all", "shadcn"):
            result["shadcn"] = {"themes": SHADCN_THEMES, "adapter": "react", "description": "shadcn/ui themes for React SPAs"}
        return ThemeInfoOutput(**result)
