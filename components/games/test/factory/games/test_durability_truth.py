"""Games health and config schema tell the truth about persistence (#384)."""
from __future__ import annotations

import asyncio

from factory.games.runtime.runtime import GamesRuntime
from factory.games.server import create_mcp_server


def _tools(runtime):
    server = create_mcp_server(runtime)
    return {t.name: t.fn for t in asyncio.run(server.list_tools())}


def test_health_reports_durable_false_for_memory() -> None:
    health = GamesRuntime({"store_backend": "memory"}).health_check()
    assert health["durable"] is False


def test_config_schema_offers_every_backend_and_game_type() -> None:
    schema = _tools(GamesRuntime({}))["describe_config_schema"]().data.properties
    assert schema["store_backend"]["enum"] == GamesRuntime.available_backends()
    assert schema["default_game_type"]["enum"] == GamesRuntime.available_game_types()
