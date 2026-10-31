"""Typed deterministic MCP tools for Auth."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, fail

from .contracts.models import CapabilitiesOutput, ConfigSchemaOutput, EmptyInput, HealthOutput

if TYPE_CHECKING:
    from ..runtime.runtime import AuthRuntime


def register(mcp: Any, runtime: "AuthRuntime") -> None:
    """Register deterministic tools with strict public contracts."""

    @mcp.tool(name="auth.get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return CapabilitiesOutput.model_validate(runtime.get_capabilities())

    @mcp.tool(name="auth.health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        try:
            raw = runtime.health_check()
            connectivity = raw.get("backend_connectivity", {})
            error = raw.get("last_backend_error")
            return HealthOutput(
                service_name=raw["service_name"], backend_selected=raw["backend_selected"],
                backend_configured=bool(connectivity.get("attempted", False)),
                connectivity_attempted=bool(connectivity.get("attempted", False)),
                connectivity_ok=connectivity.get("ok"),
                error="backend_unavailable" if error else None,
            )
        except Exception:
            return fail("auth_backend_error")

    @mcp.tool(name="auth.describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ConfigSchemaOutput.model_validate(runtime.describe_config_schema())
