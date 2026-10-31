"""Games runtime — manages game rules adapters and session store.

Usage:
    runtime = GamesRuntime()
    rules = runtime.get_rules("connect_four")
    store = runtime.get_store()
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from factory.mcp_utils.runtime.tool_failure import SafeDiagnostic

from . import event_emitter
from .ports import GameRules, GameState, GameStore, MoveResult

logger = logging.getLogger(__name__)


class GamesRuntime:
    """Factory for game rules and session storage."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._store: GameStore | None = None
        self._rules: dict[str, GameRules] = {}

    def get_rules(self, game_type: str = "connect_four") -> GameRules:
        if game_type not in self._rules:
            self._rules[game_type] = self._create_rules(game_type)
        return self._rules[game_type]

    def get_store(self) -> GameStore:
        if self._store is None:
            self._store = self._create_store()
        return self._store

    def _create_rules(self, game_type: str) -> GameRules:
        if game_type == "connect_four":
            from .adapters.connect_four import ConnectFourRules
            return ConnectFourRules()
        if game_type == "ctf_challenge":
            from .adapters.ctf_challenge import CTFChallengeRules
            return CTFChallengeRules()
        if game_type == "sql_injection":
            from .adapters.sql_injection import SQLInjectionRules
            return SQLInjectionRules()
        if game_type == "xss_hunter":
            from .adapters.xss_hunter import XSSHunterRules
            return XSSHunterRules()
        if game_type == "command_injection":
            from .adapters.command_injection import CommandInjectionRules
            return CommandInjectionRules()
        if game_type == "ssti":
            from .adapters.ssti import SSTIRules
            return SSTIRules()
        if game_type == "idor_detective":
            from .adapters.idor_detective import IDORDetectiveRules
            return IDORDetectiveRules()
        if game_type == "path_traversal":
            from .adapters.path_traversal import PathTraversalRules
            return PathTraversalRules()
        if game_type == "finding_triage":
            from .adapters.finding_triage import FindingTriageRules
            return FindingTriageRules()
        raise SafeDiagnostic(
            f"Unknown game type: {game_type}. Available: {self.available_game_types()}")

    def _create_store(self) -> GameStore:
        backend = self._config.get("store_backend", "memory")
        if backend == "memory":
            from .adapters.memory_store import MemoryGameStore
            return MemoryGameStore()
        if backend == "graph":
            from .adapters.graph_store import GraphGameStore
            return GraphGameStore()
        raise SafeDiagnostic(
            f"Unknown store backend: {backend}. Available: {self.available_backends()}")

    def create_game(
        self, game_type: str = "connect_four",
        config: dict[str, Any] | None = None,
        player_names: dict[int, str] | None = None,
    ) -> GameState:
        rules = self.get_rules(game_type)
        game_id = str(uuid.uuid4())[:8]
        game_config = dict(config or {})
        state = rules.create_initial_state(game_id, game_config)
        state.config = {**game_config, **state.config}
        state.players = player_names or {1: "Player 1", 2: "Player 2"}
        self.get_store().save(state)
        event_emitter.emit("game.created", {
            "game_id": state.game_id,
            "entity_id": f"game-{state.game_id}",
            "game_type": game_type,
            "players": state.players,
            "config": state.config,
            "run_id": state.config.get("run_id"),
            "graph_id": state.config.get("graph_id"),
            "target_app": state.config.get("target_app"),
        })
        return state

    def make_move(
        self, game_id: str, player: int, move: dict[str, Any],
    ) -> MoveResult:
        store = self.get_store()
        state = store.load(game_id)
        if state is None:
            return MoveResult(valid=False, error=f"Game {game_id} not found")
        rules = self.get_rules(state.game_type)
        result = rules.apply_move(state, player, move)
        if result.valid and result.state:
            store.save(result.state)
            event_emitter.emit("game.move", {
                "game_id": game_id,
                "entity_id": f"game-{game_id}",
                "game_type": result.state.game_type,
                "player": player,
                "move": move,
                "reward": result.reward,
                "terminal": result.terminal,
                "run_id": result.state.config.get("run_id"),
                "graph_id": result.state.config.get("graph_id"),
                "target_app": result.state.config.get("target_app"),
            })
            if result.terminal:
                event_emitter.emit("game.finished", {
                    "game_id": game_id,
                    "entity_id": f"game-{game_id}",
                    "game_type": result.state.game_type,
                    "winner": result.state.winner,
                    "reward": result.reward,
                    "move_count": len(result.state.move_history),
                    "move_history": result.state.move_history,
                    "config": result.state.config,
                    "players": result.state.players,
                    "run_id": result.state.config.get("run_id"),
                    "graph_id": result.state.config.get("graph_id"),
                    "target_app": result.state.config.get("target_app"),
                })
        return result

    def get_game(self, game_id: str) -> GameState | None:
        return self.get_store().load(game_id)

    def list_games(
        self, status: str | None = None, limit: int = 20,
    ) -> list[GameState]:
        return self.get_store().list_games(status=status, limit=limit)

    def legal_moves(self, game_id: str) -> list[dict[str, Any]]:
        state = self.get_store().load(game_id)
        if state is None:
            return []
        return self.get_rules(state.game_type).legal_moves(state)

    def evaluate(self, game_id: str) -> dict[str, Any]:
        state = self.get_store().load(game_id)
        if state is None:
            return {"error": "Game not found"}
        return self.get_rules(state.game_type).evaluate(state)

    def health_check(self) -> dict[str, Any]:
        store = self.get_store()
        h = store.health_check()
        return {"healthy": h.healthy, "backend": h.backend,
                "active_games": h.active_games}

    @staticmethod
    def available_game_types() -> list[str]:
        return [
            "connect_four", "ctf_challenge",
            "sql_injection", "xss_hunter", "command_injection", "ssti",
            "idor_detective", "path_traversal", "finding_triage",
        ]

    @staticmethod
    def available_backends() -> list[str]:
        return ["memory", "graph"]


_runtime: GamesRuntime | None = None


def get_runtime() -> GamesRuntime:
    global _runtime
    if _runtime is None:
        import os
        backend = os.environ.get("GAMES_PERSISTENCE", "memory")
        _runtime = GamesRuntime({"store_backend": backend})
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None
