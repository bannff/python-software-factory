"""MCP prompts for auth module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import (
    get_configure_keycloak_prompt,
    get_debug_token_prompt,
    get_setup_multitenancy_prompt,
)

if TYPE_CHECKING:
    from ..runtime.runtime import AuthRuntime


def register(mcp: Any, runtime: "AuthRuntime") -> None:
    """Register MCP prompts for auth."""

    @mcp.prompt()
    def configure_keycloak(
        name: str = "default",
        base_url: str = "http://localhost:8180",
        realm: str = "master",
    ) -> str:
        """Guide for configuring a Keycloak backend.

        Args:
            name: Backend configuration name
            base_url: Keycloak server URL
            realm: Keycloak realm name
        """
        return get_configure_keycloak_prompt(name, base_url, realm)

    @mcp.prompt()
    def debug_token(
        token_type: str = "access_token",
        error: str = "unknown",
    ) -> str:
        """Guide for debugging token verification issues.

        Args:
            token_type: Type of token (access_token, refresh_token)
            error: Error type encountered
        """
        return get_debug_token_prompt(token_type, error)

    @mcp.prompt()
    def setup_multitenancy() -> str:
        """Guide for setting up multi-tenant authentication."""
        return get_setup_multitenancy_prompt()
