"""Abstract ports for games brick.

Ports define what capabilities the game engine needs.
GameRules is the polymorphic interface — each game type implements it.
GameStore handles persistence of game sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class GameHealth:
    """Health status for a game backend."""
    healthy: bool
    backend: str
    active_games: int = 0
    message: str = ""


@dataclass
class GameState:
    """Serializable snapshot of a game."""
    game_id: str
    game_type: str
    board: list[list[int]]
    current_player: int
    status: str  # waiting, active, finished, draw
    winner: int | None = None
    move_history: list[dict[str, Any]] = field(default_factory=list)
    players: dict[int, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_type": self.game_type,
            "board": self.board,
            "current_player": self.current_player,
            "status": self.status,
            "winner": self.winner,
            "move_history": self.move_history,
            "players": self.players,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "move_count": len(self.move_history),
        }


@dataclass
class MoveResult:
    """Result of applying a move."""
    valid: bool
    state: GameState | None = None
    error: str | None = None
    reward: dict[int, float] = field(default_factory=dict)
    terminal: bool = False
    info: dict[str, Any] = field(default_factory=dict)


class GameRules(Protocol):
    """Port: Game rules engine (polymorphic per game type)."""

    @property
    def game_type(self) -> str: ...

    def create_initial_state(
        self, game_id: str, config: dict[str, Any] | None = None,
    ) -> GameState: ...

    def legal_moves(self, state: GameState) -> list[dict[str, Any]]: ...

    def apply_move(
        self, state: GameState, player: int, move: dict[str, Any],
    ) -> MoveResult: ...

    def evaluate(self, state: GameState) -> dict[str, Any]:
        """Heuristic evaluation for RL reward shaping."""
        ...


class GameStore(Protocol):
    """Port: Game session persistence."""

    def save(self, state: GameState) -> None: ...
    def load(self, game_id: str) -> GameState | None: ...
    def list_games(
        self, status: str | None = None, limit: int = 20,
    ) -> list[GameState]: ...
    def delete(self, game_id: str) -> bool: ...
    def health_check(self) -> GameHealth: ...
