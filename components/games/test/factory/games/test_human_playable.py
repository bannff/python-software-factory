from __future__ import annotations

import asyncio

from factory.games.runtime.runtime import GamesRuntime
from factory.games.server import create_mcp_server


def test_capabilities_say_which_types_a_person_can_play() -> None:
    mcp = create_mcp_server(GamesRuntime({"store_backend": "memory"}))
    caps = asyncio.run(mcp.get_tool("get_capabilities")).fn().data
    assert caps.human_playable_game_types == ["connect_four"]
    assert set(caps.human_playable_game_types) < set(caps.game_types)
