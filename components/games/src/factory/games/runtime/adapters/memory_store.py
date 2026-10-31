"""In-memory game store adapter.

Zero-dependency store for local dev and testing.
"""

from __future__ import annotations

from typing import Any

from ..ports import GameHealth, GameState


class MemoryGameStore:
    """In-memory game session storage."""

    def __init__(self) -> None:
        self._games: dict[str, GameState] = {}

    def save(self, state: GameState) -> None:
        self._games[state.game_id] = state

    def load(self, game_id: str) -> GameState | None:
        return self._games.get(game_id)

    def list_games(
        self, status: str | None = None, limit: int = 20,
    ) -> list[GameState]:
        games = list(self._games.values())
        if status:
            games = [g for g in games if g.status == status]
        games.sort(key=lambda g: g.updated_at or "", reverse=True)
        return games[:limit]

    def delete(self, game_id: str) -> bool:
        return self._games.pop(game_id, None) is not None

    def health_check(self) -> GameHealth:
        return GameHealth(
            healthy=True,
            backend="memory",
            active_games=sum(
                1 for g in self._games.values() if g.status == "active"),
        )
