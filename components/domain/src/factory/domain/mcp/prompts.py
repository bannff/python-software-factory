"""MCP prompts for the domain brick."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime.runtime import DomainRuntime


def register(mcp: Any, runtime: "DomainRuntime") -> None:
    """Register MCP prompts for the domain brick."""

    @mcp.prompt()
    def open_domain_engagement(domain_id: str = "security") -> str:
        """Guide for opening a domain engagement.

        Args:
            domain_id: The domain to pin (e.g. security).
        """
        return (
            f"Open an engagement for the '{domain_id}' domain.\n\n"
            "1. Call domain_get_manifest(domain_id) to inspect the "
            "presentation manifest (labels, type_descriptors, theme).\n"
            "2. Call domain_open_engagement(domain_id) to pin the active "
            "domain + manifest + default persona in one call.\n"
            "3. Render using the manifest labels/palette; an unknown "
            "domain returns the generic manifest (never errors)."
        )
