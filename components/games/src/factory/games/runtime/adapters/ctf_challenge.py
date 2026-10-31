"""CTF Challenge game rules adapter.

Models a Capture The Flag challenge as a single-player game.
The agent explores a sandbox environment, executes commands,
reads/writes files, and submits flag guesses.

This adapter is a pure rules engine — actual sandbox execution
happens externally via sandbox MCP tools. The game just tracks
actions and validates flag submissions.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from ..ports import GameState, MoveResult
from ...core import STATUS_ACTIVE, STATUS_FINISHED

# Single-player CTF constants
CTF_PLAYER = 1
DEFAULT_MAX_ATTEMPTS = 20

# Valid CTF actions
CTF_ACTIONS = ("execute", "read_file", "write_file", "submit_flag")

_LEGAL_MOVES = [
    {"action": "execute", "description": "Run a shell command"},
    {"action": "read_file", "description": "Read a file"},
    {"action": "write_file", "description": "Write a file"},
    {"action": "submit_flag", "description": "Submit a flag guess"},
]


class CTFChallengeRules:
    """CTF challenge rules — single-player flag-capture game."""

    @property
    def game_type(self) -> str:
        return "ctf_challenge"

    def create_initial_state(
        self, game_id: str, config: dict[str, Any] | None = None,
    ) -> GameState:
        cfg = config or {}
        now = datetime.now(timezone.utc).isoformat()
        return GameState(
            game_id=game_id,
            game_type="ctf_challenge",
            board=[[0]],
            current_player=CTF_PLAYER,
            status=STATUS_ACTIVE,
            players={CTF_PLAYER: "agent"},
            config={
                "challenge_id": cfg.get("challenge_id", game_id),
                "description": cfg.get("description", ""),
                "difficulty": cfg.get("difficulty", "medium"),
                "category": cfg.get("category", "misc"),
                "flag_hash": cfg.get("flag_hash", ""),
                "max_attempts": cfg.get("max_attempts", DEFAULT_MAX_ATTEMPTS),
                "sandbox_env_id": cfg.get("sandbox_env_id"),
            },
            created_at=now,
            updated_at=now,
        )

    def legal_moves(self, state: GameState) -> list[dict[str, Any]]:
        if state.status != STATUS_ACTIVE:
            return []
        max_attempts = state.config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        if len(state.move_history) >= max_attempts:
            return []
        return list(_LEGAL_MOVES)

    def apply_move(
        self, state: GameState, player: int, move: dict[str, Any],
    ) -> MoveResult:
        if state.status != STATUS_ACTIVE:
            return MoveResult(valid=False, error="Game is not active")
        if player != CTF_PLAYER:
            return MoveResult(valid=False, error="CTF is single-player")

        action = move.get("action")
        if action not in CTF_ACTIONS:
            return MoveResult(
                valid=False,
                error=f"Invalid action: {action}. Must be one of {CTF_ACTIONS}",
            )

        now = datetime.now(timezone.utc).isoformat()
        state.move_history.append({"action": action, "move": move, "ts": now})
        state.updated_at = now

        max_attempts = state.config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)

        if action == "submit_flag":
            return self._handle_submit_flag(state, move, max_attempts)

        # execute / read_file / write_file — recorded only, sandbox runs externally
        if len(state.move_history) >= max_attempts:
            return self._exhaust_attempts(state)

        return MoveResult(
            valid=True, state=state,
            reward={CTF_PLAYER: 0.0}, terminal=False,
            info={"action": action},
        )

    def evaluate(self, state: GameState) -> dict[str, Any]:
        max_attempts = state.config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        used = len(state.move_history)
        return {
            "attempts_used": used,
            "attempts_remaining": max(0, max_attempts - used),
            "solved": state.winner == CTF_PLAYER,
            "category": state.config.get("category", "misc"),
            "difficulty": state.config.get("difficulty", "medium"),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_submit_flag(
        self, state: GameState, move: dict[str, Any],
        max_attempts: int,
    ) -> MoveResult:
        flag_guess = move.get("flag", "")
        guess_hash = hashlib.sha256(flag_guess.encode()).hexdigest()
        expected_hash = state.config.get("flag_hash", "")

        if guess_hash == expected_hash:
            state.status = STATUS_FINISHED
            state.winner = CTF_PLAYER
            return MoveResult(
                valid=True, state=state,
                reward={CTF_PLAYER: 1.0}, terminal=True,
                info={"action": "submit_flag", "correct": True},
            )

        # Wrong guess — check if out of attempts
        if len(state.move_history) >= max_attempts:
            return self._exhaust_attempts(state, wrong_flag=True)

        return MoveResult(
            valid=True, state=state,
            reward={CTF_PLAYER: -0.1}, terminal=False,
            info={"action": "submit_flag", "correct": False},
        )

    @staticmethod
    def _exhaust_attempts(
        state: GameState, *, wrong_flag: bool = False,
    ) -> MoveResult:
        state.status = STATUS_FINISHED
        state.winner = None
        return MoveResult(
            valid=True, state=state,
            reward={CTF_PLAYER: -1.0}, terminal=True,
            info={"exhausted": True, "wrong_flag": wrong_flag},
        )
