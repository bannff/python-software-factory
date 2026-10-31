"""MCP Prompt registration for Games brick.

Guided workflows for playing games, training agents, and debugging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any

from .templates import PROMPT_TEMPLATES

if TYPE_CHECKING:
    from ..runtime.runtime import GamesRuntime


def register(mcp: Any, get_runtime: Callable[[], "GamesRuntime"]) -> None:
    """Register all Games prompts with the MCP server."""

    @mcp.prompt()
    def play_game(game_type: str = "connect_four") -> str:
        """Generate guidance for playing a game interactively."""
        runtime = get_runtime()
        games = runtime.list_games(status="active", limit=1)
        current = f"Active games: {len(games)}" if games else "No active games"
        return PROMPT_TEMPLATES["play_game"]["template"].format(
            game_type=game_type, current_state=current)

    @mcp.prompt()
    def train_agent() -> str:
        """Generate guidance for RL training with the games brick."""
        return PROMPT_TEMPLATES["train_agent"]["template"]

    @mcp.prompt()
    def debug_game(game_id: str = "") -> str:
        """Generate guidance for debugging a game session."""
        return PROMPT_TEMPLATES["debug_game"]["template"].format(
            game_id=game_id or "<game_id>")
