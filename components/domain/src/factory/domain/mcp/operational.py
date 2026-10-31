"""Operational (stateful) MCP tools for the domain brick."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import (
    ActiveEngagementOutput, CloseEngagementOutput, EmptyInput, EngagementOutput,
    ManifestOutput, OpenEngagementInput, OpenEngagementOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import DomainRuntime


def register(mcp: Any, runtime: "DomainRuntime") -> None:
    """Register operational tools."""

    @typed_tool(mcp)
    @operational(input_model=OpenEngagementInput, output_model=OpenEngagementOutput)
    def domain_open_engagement(
        domain_id: str, persona_id: str | None = None,
    ) -> ToolResult[OpenEngagementOutput]:
        """Pin the active domain, manifest, and resolved persona in one call."""
        result = runtime.open_engagement(domain_id, persona_id)
        return ok(OpenEngagementOutput(
            engagement=EngagementOutput.model_validate(result["engagement"].model_dump()),
            manifest=ManifestOutput.model_validate(result["manifest"].model_dump()),
            persona_id=result["persona_id"],
        ))

    @typed_tool(mcp)
    @operational(input_model=EmptyInput, output_model=ActiveEngagementOutput)
    def domain_get_active_engagement() -> ToolResult[ActiveEngagementOutput]:
        """Get the active engagement, or the generic default if none."""
        engagement = runtime.get_active_engagement()
        return ok(ActiveEngagementOutput(
            active=engagement is not None,
            engagement=None if engagement is None else EngagementOutput.model_validate(engagement.model_dump()),
        ))

    @typed_tool(mcp)
    @operational(input_model=EmptyInput, output_model=CloseEngagementOutput)
    def domain_close_engagement() -> ToolResult[CloseEngagementOutput]:
        """Close the active engagement → generic manifest + persona None."""
        runtime.close_engagement()
        return ok(CloseEngagementOutput(ok=True, active=False))
