from __future__ import annotations

import asyncio

from factory.events.server import create_tool_catalog
from factory.games.mcp import dashboard_summary


def test_games_activity_reads_the_aggregator_envelope(monkeypatch) -> None:
    tools = {t.name: t.fn for t in asyncio.run(create_tool_catalog().list_tools())}
    tools["events_publish"](source="games", event_type="game.created",
                            payload={"game_id": "g1", "entity_id": "game-g1", "game_type": "connect_four"})
    envelope = tools["events_query_history"](source="games", limit=10).model_dump(mode="json")
    monkeypatch.setattr(dashboard_summary, "_get_invoker", lambda: (lambda *_a, **_k: envelope))
    rows = dashboard_summary.list_recent_activity(10)
    assert rows and rows[0]["event_type"] == "game.created"
