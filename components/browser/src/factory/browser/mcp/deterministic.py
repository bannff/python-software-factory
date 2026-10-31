"""Deterministic Browser MCP tools with strict transport contracts."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from ..core import COMPONENT_NAME, COMPONENT_VERSION
from .contracts.deterministic import (
    CapabilitiesInput,
    CapabilitiesOutput,
    ConfigSchemaInput,
    ConfigSchemaOutput,
    EngineStatusInput,
    EngineStatusOutput,
    GetSessionInput,
    GetSessionOutput,
    HealthCheckInput,
    HealthCheckOutput,
    ListSessionsInput,
    ListSessionsOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import BrowserRuntime


def register(mcp: Any, runtime: "BrowserRuntime") -> None:
    """Register deterministic tools with the MCP server."""

    @mcp.tool(name="browser.get_capabilities")
    @deterministic(input_model=CapabilitiesInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return machine-readable capabilities for browser brick."""
        return CapabilitiesOutput(
            name=COMPONENT_NAME,
            version=COMPONENT_VERSION,
            tools={
                "deterministic": [
                    "browser.get_capabilities", "browser.health_check",
                    "browser.describe_config_schema", "browser.list_sessions",
                    "browser.get_session", "browser.get_engine_status",
                ],
                "operational": [
                    "browser.engine_smoke",
                    "browser.launch", "browser.close", "browser.navigate",
                    "browser.get_content", "browser.screenshot", "browser.click",
                    "browser.type_text", "browser.evaluate",
                    "browser.wait_for_selector",
                ],
            },
            adapters=["cdp", "mock"],
            features=[
                "browser_automation", "page_navigation", "element_interaction",
                "screenshot_capture", "javascript_execution",
            ],
        )

    @mcp.tool(name="browser.get_engine_status")
    @deterministic(input_model=EngineStatusInput, output_model=EngineStatusOutput)
    def get_engine_status() -> ToolResult[EngineStatusOutput]:
        """Report the effective engine and whether CDP could run here (pure detection)."""
        import shutil
        from ..runtime.adapters.cdp_base import CDPBase, HAS_WEBSOCKETS
        from ..server import ENGINE_ENV, ENGINES, selected_engine
        found = CDPBase().chrome_path
        resolved = shutil.which(found) if found else None
        return EngineStatusOutput(
            engine=selected_engine(), available_engines=list(ENGINES),
            chrome_path=resolved, chrome_found=resolved is not None,
            websockets_available=HAS_WEBSOCKETS,
            change_hint=f"Set {ENGINE_ENV}=cdp|mock in the API environment and restart.",
        )

    @mcp.tool(name="browser.health_check")
    @deterministic(input_model=HealthCheckInput, output_model=HealthCheckOutput)
    def health_check() -> ToolResult[HealthCheckOutput]:
        """Fast readiness probe for browser brick."""
        return HealthCheckOutput.model_validate(runtime.health_check())

    @mcp.tool(name="browser.describe_config_schema")
    @deterministic(input_model=ConfigSchemaInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Describe browser configuration schema."""
        return ConfigSchemaOutput(
            type="object",
            properties={
                "headless": {"type": "boolean", "default": True},
                "timeout_ms": {"type": "integer", "default": 30000},
                "viewport_width": {"type": "integer", "default": 1280},
                "viewport_height": {"type": "integer", "default": 720},
                "user_agent": {"type": "string", "nullable": True},
                "proxy": {"type": "string", "nullable": True},
            },
        )

    @mcp.tool(name="browser.list_sessions")
    @deterministic(input_model=ListSessionsInput, output_model=ListSessionsOutput)
    def list_sessions() -> ToolResult[ListSessionsOutput]:
        """List active browser sessions."""
        sessions = runtime.list_sessions()
        return ListSessionsOutput(
            count=len(sessions),
            sessions=[session.model_dump() for session in sessions],
        )

    @mcp.tool(name="browser.get_session")
    @deterministic(input_model=GetSessionInput, output_model=GetSessionOutput)
    def get_session(session_id: str) -> ToolResult[GetSessionOutput]:
        """Get information about a specific session."""
        session = runtime.get_session(session_id)
        if session is None:
            return GetSessionOutput(
                found=False, reason=f"Session not found: {session_id}"
            )
        return GetSessionOutput(found=True, session=session.model_dump())
