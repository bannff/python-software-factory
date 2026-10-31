"""MCP Prompt registration for HTTP brick.

Prompts provide guided workflows for common tasks:
- Making HTTP requests
- Configuring HTTP clients
- Debugging failed requests
- Batch HTTP operations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES

if TYPE_CHECKING:
    from ..runtime.runtime import HTTPRuntime


def register(mcp: Any, get_runtime: Callable[[], "HTTPRuntime"]) -> None:
    """Register all HTTP prompts with the MCP server."""

    @mcp.prompt()
    def make_request(
        method: str = "GET",
        url: str = "",
        purpose: str = "",
    ) -> str:
        """Generate guidance for making an HTTP request."""
        return PROMPT_TEMPLATES["make_request"]["template"].format(
            method=method.upper(),
            method_lower=method.lower(),
            url=url or "https://api.example.com/endpoint",
            purpose=purpose or "Make an HTTP request",
        )

    @mcp.prompt()
    def configure_client(
        backend: str = "httpx",
        auth_type: str = "none",
        goal: str = "",
    ) -> str:
        """Generate guidance for configuring an HTTP client."""
        return PROMPT_TEMPLATES["configure_client"]["template"].format(
            backend=backend,
            auth_type=auth_type,
            goal=goal or "Configure HTTP client for API access",
        )

    @mcp.prompt()
    def debug_request(
        url: str = "",
        error: str = "",
        status_code: str = "",
    ) -> str:
        """Generate guidance for debugging a failed HTTP request."""
        return PROMPT_TEMPLATES["debug_request"]["template"].format(
            url=url or "https://api.example.com/endpoint",
            error=error or "Request failed",
            status_code=status_code or "unknown",
        )

    @mcp.prompt()
    def batch_requests(
        urls: str = "",
        goal: str = "",
    ) -> str:
        """Generate guidance for batch HTTP operations."""
        return PROMPT_TEMPLATES["batch_requests"]["template"].format(
            urls=urls or "- https://api.example.com/item/1\n- https://api.example.com/item/2",
            goal=goal or "Fetch multiple resources",
        )
