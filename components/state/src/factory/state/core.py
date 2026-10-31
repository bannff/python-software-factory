"""Runtime session state model with pure transitions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto

from pydantic import BaseModel, Field


class Focus(Enum):
    MENU = auto()
    GAME = auto()


class SessionState(BaseModel, frozen=True):
    """Immutable snapshot of the arcade session."""

    focus: Focus = Focus.MENU
    current_game_id: str | None = None
    last_played_id: str | None = None
    launched_at: datetime | None = None


def transition_to_game(state: SessionState, game_id: str, now: datetime) -> SessionState:
    """Pure transition: menu -> game launched."""
    return SessionState(
        focus=Focus.GAME,
        current_game_id=game_id,
        last_played_id=game_id,
        launched_at=now,
    )


def transition_to_menu(state: SessionState) -> SessionState:
    """Pure transition: game -> back to menu."""
    return SessionState(
        focus=Focus.MENU,
        current_game_id=None,
        last_played_id=state.current_game_id or state.last_played_id,
        launched_at=None,
    )
