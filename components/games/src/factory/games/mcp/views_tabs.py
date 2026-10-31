"""Action form builder for Game Arena dashboard.

Exports:
- games_action_form(): create-game form + action pane for moves

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def games_action_form() -> dict[str, Any]:
    """Create-game form with action pane for write operations."""
    return {
        "id": "games-actions-card",
        "type": "card",
        "props": {
            "title": "Game Actions",
            "icon": "🎯",
            "collapsible": True,
        },
        "children": [
            {
                "id": "games-create-form",
                "type": "form",
                "props": {
                    "tool": "games_games_create",
                    "title": "New Game",
                    "submit_label": "Create Game",
                    "fields": [
                        {
                            "name": "player1_name",
                            "label": "Player 1",
                            "type": "text",
                            "placeholder": "Player 1",
                            "tooltip": "Name for player 1 (🔴)",
                        },
                        {
                            "name": "player2_name",
                            "label": "Player 2",
                            "type": "text",
                            "placeholder": "Player 2",
                            "tooltip": "Name for player 2 (🟡)",
                        },
                        {
                            "name": "cols",
                            "label": "Columns",
                            "type": "range",
                            "min": 4, "max": 10, "value": 7,
                            "tooltip": "Board width (4–10)",
                        },
                        {
                            "name": "rows",
                            "label": "Rows",
                            "type": "range",
                            "min": 4, "max": 8, "value": 6,
                            "tooltip": "Board height (4–8)",
                        },
                    ],
                },
            },
            {
                "id": "games-action-pane",
                "type": "action_pane",
                "props": {
                    "actions": _actions(),
                    "default_action": "make-move",
                },
            },
        ],
    }


def _actions() -> list[dict[str, Any]]:
    """Write-operation actions for the games action pane."""
    return [
        {
            "id": "make-move", "label": "Make a Move", "icon": "🎯",
            "tool": "games_games_move",
            "submit_label": "Drop Token",
            "fields": [
                {"name": "game_id", "label": "Game ID", "type": "text",
                 "placeholder": "abc12345",
                 "tooltip": "ID from an active game"},
                {"name": "player", "label": "Player", "type": "select",
                 "options": [
                     {"value": "1", "label": "Player 1 (🔴)"},
                     {"value": "2", "label": "Player 2 (🟡)"},
                 ],
                 "tooltip": "Whose turn is it?"},
                {"name": "column", "label": "Column", "type": "range",
                 "min": 0, "max": 6, "value": 3,
                 "tooltip": "Column to drop token (0 = leftmost)"},
            ],
        },
        {
            "id": "evaluate-board", "label": "Evaluate Board",
            "icon": "🧠",
            "tool": "games_games_evaluate",
            "submit_label": "Evaluate",
            "fields": [
                {"name": "game_id", "label": "Game ID", "type": "text",
                 "placeholder": "abc12345",
                 "tooltip": "Run heuristic evaluation"},
            ],
        },
        {
            "id": "reset-game", "label": "Reset Game", "icon": "🔄",
            "tool": "games_games_reset",
            "submit_label": "Reset",
            "fields": [
                {"name": "game_id", "label": "Game ID", "type": "text",
                 "placeholder": "abc12345",
                 "tooltip": "Clear board — same players, fresh game"},
            ],
        },
        {
            "id": "delete-game", "label": "⚠ Delete Game", "icon": "🗑️",
            "tool": "games_games_delete",
            "submit_label": "Delete",
            "fields": [
                {"name": "game_id", "label": "Game ID", "type": "text",
                 "placeholder": "abc12345",
                 "tooltip": "Permanently remove this game session"},
            ],
        },
    ]
