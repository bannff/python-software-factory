from __future__ import annotations

import asyncio

from factory.games.runtime.runtime import GamesRuntime
from factory.games.server import create_mcp_server


def _tools():
    mcp = create_mcp_server(GamesRuntime({"store_backend": "memory"}))
    return lambda name: asyncio.run(mcp.get_tool(name)).fn


def test_a_valid_move_returns_its_typed_result() -> None:
    tool = _tools()
    game = tool("games_create")(game_type="connect_four").data
    move = tool("games_move")(game_id=game.game_id, player=1, column=3)
    assert move.ok and move.data.valid and move.data.state.current_player == 2


def test_refusals_are_typed_codes() -> None:
    tool = _tools()
    gid = tool("games_create")(game_type="connect_four").data.game_id
    assert tool("games_move")(game_id=gid, player=2, column=3).error == "not_your_turn"
    assert tool("games_move")(game_id="missing", player=1, column=3).error == "game_not_found"
    assert tool("games_move")(game_id=gid, player=1, column=99).error == "illegal_move"
    assert tool("games_reset")(game_id="missing").error == "game_not_found"
