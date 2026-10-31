"""Security-gated Browser profile authoring MCP tools."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring as authoring_decorator

from .contracts.authoring import (
    AuthoringStatusInput, AuthoringStatusOutput, DeleteProfileInput,
    DeleteProfileOutput, ListProfilesInput, ListProfilesOutput, ProfileOutput,
    UpsertProfileInput, UpsertProfileOutput, json_safe_profile,
)

if TYPE_CHECKING:
    from ..authoring import AuthoringManager
    from ..runtime.runtime import BrowserRuntime


def _profile_output(profile: dict[str, object]) -> ProfileOutput:
    """Convert a persisted profile to JSON-safe public transport data."""
    config = profile.get("config")
    try:
        safe_config = json_safe_profile(config) if config is not None else None
        return ProfileOutput(
            id=str(profile["id"]), path=str(profile["path"]), config=safe_config,
            error=profile.get("error") if isinstance(profile.get("error"), str) else None,
        )
    except ValueError:
        return ProfileOutput(
            id=str(profile["id"]), path=str(profile["path"]),
            error="Profile config is not JSON compatible",
        )


def register(
    mcp: Any,
    runtime: "BrowserRuntime",
    manager: "AuthoringManager | None",
) -> None:
    """Register authoring tools with the MCP server."""
    from ..authoring import AuthoringError

    @mcp.tool(name="browser.authoring.get_status")
    @authoring_decorator(
        input_model=AuthoringStatusInput, output_model=AuthoringStatusOutput
    )
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Get authoring status and configuration."""
        if manager is None:
            return AuthoringStatusOutput(
                enabled=False, message="Authoring tools disabled"
            )
        return AuthoringStatusOutput.model_validate(manager.get_status())

    @mcp.tool(name="browser.authoring.list_profiles")
    @authoring_decorator(
        input_model=ListProfilesInput, output_model=ListProfilesOutput
    )
    def authoring_list_profiles() -> ToolResult[ListProfilesOutput]:
        """List all browser profiles."""
        if manager is None:
            raise AuthoringError("Authoring tools disabled")
        result = manager.list_profiles()
        return ListProfilesOutput(
            profiles=[_profile_output(item) for item in result["profiles"]],
            count=result["count"],
        )

    @mcp.tool(name="browser.authoring.upsert_profile")
    @authoring_decorator(
        input_model=UpsertProfileInput, output_model=UpsertProfileOutput
    )
    def authoring_upsert_profile(
        id: str,
        config: dict[str, object],
        dry_run: bool = False,
    ) -> ToolResult[UpsertProfileOutput]:
        """Create or update a browser profile."""
        if manager is None:
            raise AuthoringError("Authoring tools disabled")
        return UpsertProfileOutput.model_validate(
            manager.upsert_profile(id=id, config=config, dry_run=dry_run)
        )

    @mcp.tool(name="browser.authoring.delete_profile")
    @authoring_decorator(
        input_model=DeleteProfileInput, output_model=DeleteProfileOutput
    )
    def authoring_delete_profile(id: str) -> ToolResult[DeleteProfileOutput]:
        """Delete a browser profile."""
        if manager is None:
            raise AuthoringError("Authoring tools disabled")
        return DeleteProfileOutput.model_validate(manager.delete_profile(id=id))
