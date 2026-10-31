"""Tests for state brick — session state transitions."""

from datetime import datetime

from factory.state.interface import Focus, SessionState, transition_to_game, transition_to_menu


def test_default_state():
    s = SessionState()
    assert s.focus == Focus.MENU
    assert s.current_game_id is None
    assert s.last_played_id is None


def test_transition_to_game():
    s = SessionState()
    now = datetime(2026, 6, 29, 12, 0, 0)
    s2 = transition_to_game(s, "kinst", now)
    assert s2.focus == Focus.GAME
    assert s2.current_game_id == "kinst"
    assert s2.last_played_id == "kinst"
    assert s2.launched_at == now


def test_transition_to_menu():
    now = datetime(2026, 6, 29, 12, 0, 0)
    s = SessionState(focus=Focus.GAME, current_game_id="kinst", last_played_id="kinst", launched_at=now)
    s2 = transition_to_menu(s)
    assert s2.focus == Focus.MENU
    assert s2.current_game_id is None
    assert s2.last_played_id == "kinst"
    assert s2.launched_at is None


def test_state_is_frozen():
    s = SessionState()
    try:
        s.focus = Focus.GAME  # type: ignore
        assert False, "Should be frozen"
    except Exception:
        pass
