"""Tests for Connect Four game rules and runtime."""

from factory.games.runtime.runtime import GamesRuntime
from factory.games.core import PLAYER_1, PLAYER_2, STATUS_ACTIVE, STATUS_FINISHED


def test_create_game():
    rt = GamesRuntime()
    state = rt.create_game("connect_four")
    assert state.status == STATUS_ACTIVE
    assert state.current_player == PLAYER_1
    assert len(state.board) == 6
    assert len(state.board[0]) == 7


def test_legal_moves():
    rt = GamesRuntime()
    state = rt.create_game("connect_four")
    moves = rt.legal_moves(state.game_id)
    assert len(moves) == 7
    assert all("column" in m for m in moves)


def test_make_move():
    rt = GamesRuntime()
    state = rt.create_game("connect_four")
    result = rt.make_move(state.game_id, PLAYER_1, {"column": 3})
    assert result.valid
    assert result.state.current_player == PLAYER_2
    assert result.state.board[5][3] == PLAYER_1


def test_invalid_move_wrong_player():
    rt = GamesRuntime()
    state = rt.create_game("connect_four")
    result = rt.make_move(state.game_id, PLAYER_2, {"column": 3})
    assert not result.valid
    assert "Not player" in result.error


def test_win_vertical():
    rt = GamesRuntime()
    state = rt.create_game("connect_four")
    gid = state.game_id
    # P1 stacks column 0, P2 stacks column 1
    for _ in range(3):
        rt.make_move(gid, PLAYER_1, {"column": 0})
        rt.make_move(gid, PLAYER_2, {"column": 1})
    result = rt.make_move(gid, PLAYER_1, {"column": 0})
    assert result.terminal
    assert result.state.status == STATUS_FINISHED
    assert result.state.winner == PLAYER_1
    assert result.reward[PLAYER_1] == 1.0
    assert result.reward[PLAYER_2] == -1.0


def test_evaluate():
    rt = GamesRuntime()
    state = rt.create_game("connect_four")
    rt.make_move(state.game_id, PLAYER_1, {"column": 3})
    ev = rt.evaluate(state.game_id)
    assert "scores" in ev
