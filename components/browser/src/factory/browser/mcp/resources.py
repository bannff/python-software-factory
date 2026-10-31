"""MCP Resource registration for browser brick.

Resources expose static/queryable data:
- Schemas for browser configuration and sessions
- Documentation on adapters and usage
- Live session data
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

from .docs import DOCS

if TYPE_CHECKING:
    from ..runtime.runtime import BrowserRuntime


def register(mcp: Any, runtime: "BrowserRuntime") -> None:
    """Register all browser resources with the MCP server."""
    from ..runtime.models import BrowserConfig, SessionInfo

    @mcp.resource("browser://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for browser configuration."""
        return json.dumps(BrowserConfig.model_json_schema(), indent=2)

    @mcp.resource("browser://schemas/session")
    def resource_session_schema() -> str:
        """Get the JSON schema for browser sessions."""
        return json.dumps(SessionInfo.model_json_schema(), indent=2)

    @mcp.resource("browser://docs")
    def resource_docs_list() -> str:
        """List available browser documentation."""
        docs = [{"name": k, "title": k.replace("_", " ").title()} for k in DOCS.keys()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("browser://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get browser documentation by name."""
        if doc_name in DOCS:
            return DOCS[doc_name]
        available = list(DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    @mcp.resource("browser://sessions")
    def resource_sessions() -> str:
        """List active browser sessions."""
        sessions = runtime.list_sessions()
        return json.dumps(
            {"sessions": [s.model_dump() for s in sessions], "count": len(sessions)},
            indent=2,
        )

    @mcp.resource("browser://backends")
    def resource_backends() -> str:
        """List available browser backends."""
        return json.dumps({
            "backends": [
                {"name": "cdp", "description": "Chrome DevTools Protocol (direct)"},
                {"name": "playwright", "description": "Playwright automation library"},
                {"name": "mock", "description": "Mock adapter for testing"},
            ],
        }, indent=2)

    @mcp.resource("browser://health")
    def resource_health() -> str:
        """Get browser health status."""
        sessions = runtime.list_sessions()
        active_count = len([s for s in sessions if s.status == "active"])
        return json.dumps({
            "healthy": True,
            "adapter": runtime.adapter.__class__.__name__,
            "sessions": {
                "total": len(sessions),
                "active": active_count,
            },
            "message": "Browser runtime operational",
        }, indent=2)

    @mcp.resource("browser://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": [
                "foreman_info", "foreman_check",
                "foreman_guardian_check", "foreman_get_repo_guardrails",
            ],
            "foreman_resources": [
                "foreman://docs", "foreman://bricks", "foreman://schema/brick-yaml",
            ],
        }, indent=2)
