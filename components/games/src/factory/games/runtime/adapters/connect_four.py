"""Connect Four game rules adapter.

A classic two-player connection game. Drop tokens into columns,
first to connect four in a row (horizontal, vertical, diagonal) wins.

RL-ready: provides reward signals and heuristic evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..ports import GameState, MoveResult
from ...core import (
    DEFAULT_COLS, DEFAULT_ROWS, DEFAULT_WIN_LENGTH,
    EMPTY, PLAYER_1, PLAYER_2,
    STATUS_ACTIVE, STATUS_DRAW, STATUS_FINISHED,
)


class ConnectFourRules:
    """Connect Four game rules implementation."""

    @property
    def game_type(self) -> str:
        return "connect_four"

    def create_initial_state(
        self, game_id: str, config: dict[str, Any] | None = None,
    ) -> GameState:
        cfg = config or {}
        rows = cfg.get("rows", DEFAULT_ROWS)
        cols = cfg.get("cols", DEFAULT_COLS)
        now = datetime.now(timezone.utc).isoformat()
        board = [[EMPTY] * cols for _ in range(rows)]
        return GameState(
            game_id=game_id,
            game_type="connect_four",
            board=board,
            current_player=PLAYER_1,
            status=STATUS_ACTIVE,
            config={"rows": rows, "cols": cols,
                    "win_length": cfg.get("win_length", DEFAULT_WIN_LENGTH)},
            created_at=now,
            updated_at=now,
        )

    def legal_moves(self, state: GameState) -> list[dict[str, Any]]:
        if state.status != STATUS_ACTIVE:
            return []
        cols = state.config.get("cols", DEFAULT_COLS)
        moves = []
        for col in range(cols):
            if state.board[0][col] == EMPTY:
                moves.append({"column": col})
        return moves

    def apply_move(
        self, state: GameState, player: int, move: dict[str, Any],
    ) -> MoveResult:
        if state.status != STATUS_ACTIVE:
            return MoveResult(valid=False, error="Game is not active")
        if player != state.current_player:
            return MoveResult(valid=False, error=f"Not player {player}'s turn")

        col = move.get("column")
        cols = state.config.get("cols", DEFAULT_COLS)
        rows = state.config.get("rows", DEFAULT_ROWS)

        if col is None or not (0 <= col < cols):
            return MoveResult(valid=False, error=f"Invalid column: {col}")
        if state.board[0][col] != EMPTY:
            return MoveResult(valid=False, error=f"Column {col} is full")

        # Drop the token
        row = self._drop_row(state.board, col, rows)
        state.board[row][col] = player
        now = datetime.now(timezone.utc).isoformat()
        state.move_history.append(
            {"player": player, "column": col, "row": row, "ts": now})
        state.updated_at = now

        # Check win / draw
        win_len = state.config.get("win_length", DEFAULT_WIN_LENGTH)
        reward: dict[int, float] = {PLAYER_1: 0.0, PLAYER_2: 0.0}
        terminal = False

        if self._check_win(state.board, row, col, player, win_len):
            state.status = STATUS_FINISHED
            state.winner = player
            reward[player] = 1.0
            other = PLAYER_2 if player == PLAYER_1 else PLAYER_1
            reward[other] = -1.0
            terminal = True
        elif not any(state.board[0][c] == EMPTY for c in range(cols)):
            state.status = STATUS_DRAW
            reward = {PLAYER_1: 0.0, PLAYER_2: 0.0}
            terminal = True
        else:
            state.current_player = (
                PLAYER_2 if player == PLAYER_1 else PLAYER_1)

        return MoveResult(
            valid=True, state=state, reward=reward,
            terminal=terminal, info={"row": row, "column": col},
        )

    def evaluate(self, state: GameState) -> dict[str, Any]:
        """Heuristic board evaluation for RL reward shaping."""
        win_len = state.config.get("win_length", DEFAULT_WIN_LENGTH)
        scores = {PLAYER_1: 0.0, PLAYER_2: 0.0}
        rows = len(state.board)
        cols = len(state.board[0]) if rows else 0
        # Count streaks of length 2 and 3
        for r in range(rows):
            for c in range(cols):
                p = state.board[r][c]
                if p == EMPTY:
                    continue
                for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                    length = 1
                    nr, nc = r + dr, c + dc
                    while (0 <= nr < rows and 0 <= nc < cols
                           and state.board[nr][nc] == p
                           and length < win_len):
                        length += 1
                        nr += dr
                        nc += dc
                    if length >= 2:
                        scores[p] += length ** 2
        return {"scores": scores, "move_count": len(state.move_history)}

    @staticmethod
    def _drop_row(board: list[list[int]], col: int, rows: int) -> int:
        for r in range(rows - 1, -1, -1):
            if board[r][col] == EMPTY:
                return r
        return 0  # should not reach here if validated

    @staticmethod
    def _check_win(
        board: list[list[int]], row: int, col: int,
        player: int, win_length: int,
    ) -> bool:
        rows, cols = len(board), len(board[0])
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            count = 1
            for sign in (1, -1):
                nr, nc = row + sign * dr, col + sign * dc
                while (0 <= nr < rows and 0 <= nc < cols
                       and board[nr][nc] == player):
                    count += 1
                    nr += sign * dr
                    nc += sign * dc
            if count >= win_length:
                return True
        return False
