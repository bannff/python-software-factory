"""MCP Resource registration for Games brick.

Resources expose schemas, docs, and live data.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from typing import Any

from .docs import GAMES_DOCS

if TYPE_CHECKING:
    from ..runtime.runtime import GamesRuntime


def register(mcp: Any, get_runtime: Callable[[], "GamesRuntime"]) -> None:
    """Register all Games resources with the MCP server."""

    @mcp.resource("games://schemas/config")
    def resource_config_schema() -> str:
        """JSON schema for games configuration."""
        return json.dumps({
            "type": "object",
            "properties": {
                "default_game_type": {"type": "string", "enum": ["connect_four"]},
                "store_backend": {"type": "string", "enum": ["memory"]},
                "rows": {"type": "integer", "default": 6},
                "cols": {"type": "integer", "default": 7},
                "win_length": {"type": "integer", "default": 4},
            },
        }, indent=2)

    @mcp.resource("games://schemas/game")
    def resource_game_schema() -> str:
        """JSON schema for a game state."""
        return json.dumps({
            "type": "object",
            "properties": {
                "game_id": {"type": "string"},
                "game_type": {"type": "string"},
                "board": {"type": "array", "items": {"type": "array"}},
                "current_player": {"type": "integer"},
                "status": {"type": "string"},
                "winner": {"type": "integer", "nullable": True},
                "move_history": {"type": "array"},
            },
        }, indent=2)

    @mcp.resource("games://docs")
    def resource_docs_list() -> str:
        """List available games documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in GAMES_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("games://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get games documentation by name."""
        if doc_name in GAMES_DOCS:
            return GAMES_DOCS[doc_name]["content"]
        return f"Unknown doc: {doc_name}. Available: {list(GAMES_DOCS.keys())}"

    @mcp.resource("games://health")
    def resource_health() -> str:
        """Get games health status."""
        runtime = get_runtime()
        return json.dumps(runtime.health_check(), indent=2)

    @mcp.resource("games://backends")
    def resource_backends() -> str:
        """List available game backends."""
        from ..runtime.runtime import GamesRuntime
        return json.dumps({
            "game_types": GamesRuntime.available_game_types(),
            "store_backends": GamesRuntime.available_backends(),
        }, indent=2)

    @mcp.resource("games://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "related_bricks": {
                "machine_learning": "Use for RL experiment tracking",
                "evals": "Use for agent benchmarking via games",
                "agent": "Use for AI game players",
            },
        }, indent=2)
