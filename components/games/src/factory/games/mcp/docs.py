"""Documentation content for games brick."""

GAMES_DOCS: dict[str, dict[str, str]] = {
    "overview": {
        "title": "Games Brick Overview",
        "content": (
            "# Games Brick\n\n"
            "Turn-based game engine with pluggable rules and RL-ready interface.\n\n"
            "## Game Types\n"
            "- **connect_four**: Classic 2-player connection game (configurable board)\n\n"
            "## Architecture\n"
            "- `GameRules` Protocol: polymorphic per game type\n"
            "- `GameStore` Protocol: pluggable persistence\n"
            "- RL interface: `legal_moves`, `apply_move` (with reward), `evaluate`\n\n"
            "## RL Integration\n"
            "Each move returns a reward dict `{player_id: float}` and a terminal flag.\n"
            "Use `games_evaluate` for heuristic reward shaping during training."
        ),
    },
    "adapters": {
        "title": "Available Adapters",
        "content": (
            "# Game Adapters\n\n"
            "## Rules Adapters\n"
            "- **connect_four**: 2-player, variable board, gravity-based\n\n"
            "## Store Adapters\n"
            "- **memory**: In-process dict (default, no deps)\n"
        ),
    },
}
