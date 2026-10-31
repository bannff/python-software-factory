"""MCP Prompt registration for Events brick.

Prompts provide guided workflows for common tasks:
- Creating new subscriptions
- Debugging event flow issues
- Configuring storage backends
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES, STORAGE_GUIDES

if TYPE_CHECKING:
    from pathlib import Path
    from ..runtime.runtime import EventsRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "EventsRuntime"],
    get_config_dir: Callable[[], "Path"],
) -> None:
    """Register all Events prompts with the MCP server."""

    @mcp.prompt()
    def create_subscription(
        name: str,
        event_type: str,
        handler: str,
        purpose: str = "",
    ) -> str:
        """Generate guidance for creating a new event subscription."""
        sub_id = name.lower().replace(" ", "-").replace("_", "-")
        
        return PROMPT_TEMPLATES["create_subscription"]["template"].format(
            name=name,
            id=sub_id,
            event_type=event_type,
            handler=handler,
            purpose=purpose or f"Handle {event_type} events",
        )

    @mcp.prompt()
    def debug_events(event_type: str = "", issue: str = "") -> str:
        """Generate guidance for debugging event flow issues."""
        return PROMPT_TEMPLATES["debug_events"]["template"].format(
            event_type=event_type or "*",
            issue=issue or "Events not being processed as expected",
        )

    @mcp.prompt()
    def configure_storage(backend: str = "redis") -> str:
        """Generate guidance for configuring event storage backend."""
        backend = backend.lower()
        if backend not in STORAGE_GUIDES:
            backend = "redis"
        
        guide = STORAGE_GUIDES[backend]
        current_config = f"Config dir: {get_config_dir()}"
        
        return PROMPT_TEMPLATES["configure_storage"]["template"].format(
            backend=backend,
            current_config=current_config,
            setup_guide=guide["setup_guide"],
            backend_config=guide["backend_config"],
        )
