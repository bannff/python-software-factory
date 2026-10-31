"""Graph-backed game store via MCP tool invoker.

Persists GameSession entities to Neo4j through the graph brick's
MCP tools. Uses the service registry pattern — no direct graph
brick imports, no Neo4j driver usage.

Complex types (board, move_history, players, config) are JSON-
serialized to strings since Neo4j properties must be primitives.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from factory.mcp_utils.interface import normalize_correlation

from ..ports import GameHealth, GameState

logger = logging.getLogger(__name__)

_ENTITY_TYPE = "GameSession"
_ID_PREFIX = "game-"

# Fields that need JSON serialization for Neo4j storage
_JSON_FIELDS = frozenset({"board", "move_history", "players", "config"})


def _get_invoker():
    """Get the MCP tool invoker from the service registry.

    Returns None quickly if unavailable — never blocks.
    """
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    """Invoke a graph brick tool via the service registry."""
    invoker = _get_invoker()
    if invoker is None:
        raise RuntimeError("No tool invoker available for graph store")
    return invoker(tool_name, **kwargs)


def _entity_id(game_id: str) -> str:
    """Build the graph entity ID for a game session."""
    return f"{_ID_PREFIX}{game_id}"


def _serialize_props(state: GameState) -> dict[str, Any]:
    """Convert GameState to Neo4j-safe properties dict."""
    raw = state.to_dict()
    props: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _JSON_FIELDS:
            props[key] = json.dumps(value)
        elif value is not None:
            props[key] = value
    for key, value in normalize_correlation(state.config, {"game_id": state.game_id, "entity_id": _entity_id(state.game_id)}).items():
        props.setdefault(key, value)
    return props


def _deserialize_state(entity: dict[str, Any]) -> GameState:
    """Reconstruct a GameState from graph entity properties."""
    props = entity.get("properties", entity)
    board = json.loads(props.get("board", "[]"))
    move_history = json.loads(props.get("move_history", "[]"))
    players_raw = json.loads(props.get("players", "{}"))
    config = json.loads(props.get("config", "{}"))
    # Neo4j may return player keys as strings — coerce to int
    players = {int(k): v for k, v in players_raw.items()}
    winner = props.get("winner")
    if winner is not None:
        winner = int(winner)
    return GameState(
        game_id=props.get("game_id", ""),
        game_type=props.get("game_type", ""),
        board=board,
        current_player=int(props.get("current_player", 1)),
        status=props.get("status", "active"),
        winner=winner,
        move_history=move_history,
        players=players,
        config=config,
        created_at=props.get("created_at", ""),
        updated_at=props.get("updated_at", ""),
    )


class GraphGameStore:
    """Persist game sessions to Neo4j via graph brick MCP tools."""

    def save(self, state: GameState) -> None:
        """Save or update a game session (MERGE semantics)."""
        try:
            _invoke(
                "graph_graph_add_entity",
                entity_id=_entity_id(state.game_id),
                entity_type=_ENTITY_TYPE,
                properties=_serialize_props(state),
            )
        except Exception as e:
            logger.error("Failed to save game %s: %s", state.game_id, e)

    def load(self, game_id: str) -> GameState | None:
        """Load a game session by ID."""
        try:
            result = _invoke(
                "graph_graph_get_entity",
                entity_id=_entity_id(game_id),
            )
            if not result or not result.ok or result.data is None:
                return None
            if not result.data.found or result.data.entity is None:
                return None
            return _deserialize_state(result.data.entity.model_dump())
        except Exception as e:
            logger.error("Failed to load game %s: %s", game_id, e)
            return None

    def list_games(
        self, status: str | None = None, limit: int = 20,
    ) -> list[GameState]:
        """List game sessions, optionally filtered by status."""
        try:
            result = _invoke(
                "graph_graph_find_entities",
                entity_type=_ENTITY_TYPE,
                limit=limit,
            )
            if not result or not result.ok or result.data is None:
                return []
            games = [_deserialize_state(entity.model_dump()) for entity in result.data.entities]
            if status:
                games = [g for g in games if g.status == status]
            return games
        except Exception as e:
            logger.error("Failed to list games: %s", e)
            return []

    def delete(self, game_id: str) -> bool:
        """Delete a game session from the graph."""
        try:
            result = _invoke(
                "graph_graph_delete_entity",
                entity_id=_entity_id(game_id),
            )
            return bool(result and result.ok and result.data is not None and result.data.success)
        except Exception as e:
            logger.error("Failed to delete game %s: %s", game_id, e)
            return False

    def health_check(self) -> GameHealth:
        """Check graph brick connectivity."""
        try:
            result = _invoke("graph_graph_health_check")
            data = getattr(result, "data", None)
            return GameHealth(healthy=bool(result and result.ok and data and data.healthy),
                              backend="graph", active_games=0)
        except Exception as e:
            return GameHealth(
                healthy=False, backend="graph", message=str(e),
            )
