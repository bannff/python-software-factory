"""Prompt templates for games brick."""

PROMPT_TEMPLATES: dict[str, dict[str, str]] = {
    "play_game": {
        "description": "Guide for playing a game interactively",
        "template": (
            "# Play {game_type}\n\n"
            "## Current State\n{current_state}\n\n"
            "## Steps\n"
            "1. Create a game: `games_create(game_type=\"{game_type}\")`\n"
            "2. Check legal moves: `games_legal_moves(game_id=\"...\")`\n"
            "3. Make a move: `games_move(game_id=\"...\", player=1, column=3)`\n"
            "4. Alternate players until terminal\n"
        ),
    },
    "train_agent": {
        "description": "Guide for RL training with the games brick",
        "template": (
            "# RL Training with Games Brick\n\n"
            "## Environment Interface\n"
            "- `games_create` → initial state (reset)\n"
            "- `games_legal_moves` → action space\n"
            "- `games_move` → step (returns reward + terminal)\n"
            "- `games_evaluate` → heuristic reward shaping\n\n"
            "## Integration with ML Brick\n"
            "Use `machine_learning` brick for experiment tracking:\n"
            "- Log episode rewards as metrics\n"
            "- Track win rates across training runs\n"
            "- Compare agent strategies\n"
        ),
    },
    "debug_game": {
        "description": "Guide for debugging game issues",
        "template": (
            "# Debug Game Session\n\n"
            "## Game: {game_id}\n\n"
            "## Diagnostic Steps\n"
            "1. Get state: `games_get_state(game_id=\"{game_id}\")`\n"
            "2. Check legal moves: `games_legal_moves(game_id=\"{game_id}\")`\n"
            "3. Review move history in the state response\n"
            "4. Evaluate position: `games_evaluate(game_id=\"{game_id}\")`\n"
        ),
    },
}
