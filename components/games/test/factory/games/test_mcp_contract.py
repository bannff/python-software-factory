"""Tests for games MCP dashboard contract and correlated views."""

import asyncio
from types import SimpleNamespace

import pytest
from factory.graph.mcp.core_models import EntityData
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_result import ToolResult

from factory.games.runtime.runtime import GamesRuntime
from factory.games.server import create_mcp_server


class TestGamesMCPContract:
    @pytest.fixture
    def runtime(self) -> GamesRuntime:
        return GamesRuntime({"store_backend": "memory"})

    @pytest.fixture
    def mcp(self, runtime: GamesRuntime):
        return create_mcp_server(runtime)

    def test_has_dashboard_tools(self, mcp) -> None:
        tool_names = [tool.name for tool in asyncio.run(mcp.list_tools())]
        assert "games_get_dashboard_summary" in tool_names
        assert "games_get_game_activity" in tool_names
        assert "games_get_game_graph_context" in tool_names
        assert "games_get_views" in tool_names

    @pytest.mark.asyncio
    async def test_dashboard_summary_and_views(self, mcp, runtime: GamesRuntime) -> None:
        published: list[dict[str, object]] = []

        def fake_invoker(tool_name: str, **kwargs):
            if tool_name == "events_publish":
                payload = kwargs.get("payload", {})
                published.append({
                    "event_id": f"evt-{len(published) + 1}",
                    "event_type": kwargs.get("event_type", ""),
                    "source": kwargs.get("source", ""),
                    "timestamp": "2026-05-06T00:00:00+00:00",
                    "payload": payload,
                    "metadata": kwargs.get("attributes", {}),
                })
                return {"event_id": f"evt-{len(published)}", "status": "published"}
            if tool_name == "events_query_history":
                entries = list(reversed(published))
                source = kwargs.get("source")
                if source:
                    entries = [entry for entry in entries if entry.get("source") == source]
                payload_key = kwargs.get("payload_key")
                payload_value = kwargs.get("payload_value")
                if payload_key is not None:
                    entries = [
                        entry
                        for entry in entries
                        if str((entry.get("payload") or {}).get(payload_key)) == str(payload_value)
                    ]
                limit = int(kwargs.get("limit", len(entries)))
                return ToolResult(data=SimpleNamespace(entries=entries[:limit]))
            if tool_name == "graph_find_entities":
                return ToolResult(data=SimpleNamespace(entities=[EntityData(
                    id=f"game-{game.game_id}", type="GameSession",
                    properties={
                        "game_id": game.game_id, "game_type": game.game_type,
                        "status": "active", "run_id": "run-123", "graph_id": "graph-123",
                        "target_app": "WebGoat",
                    },
                )]))
            if tool_name == "graph_get_entity":
                entity_id = str(kwargs.get("entity_id", ""))
                entity = None
                if entity_id == f"game-{game.game_id}":
                    entity = EntityData(id=entity_id, type="GameSession", properties={
                        "game_id": game.game_id, "game_type": game.game_type,
                        "status": "active", "run_id": "run-123", "graph_id": "graph-123",
                        "target_app": "WebGoat",
                    })
                return ToolResult(data=SimpleNamespace(entity=entity))
            if tool_name == "graph_get_neighbors":
                return ToolResult(data=SimpleNamespace(neighbors=[
                    EntityData(id="workflow-run-123", type="WorkflowRun",
                               properties={"run_id": "run-123", "status": "completed"}),
                    EntityData(id="eval-run-123", type="EvaluationRun",
                               properties={"run_id": "run-123", "status": "passed"}),
                ]))
            raise AssertionError(f"unexpected tool: {tool_name}")

        previous_invoker = get_service("tool_invoker")
        set_service("tool_invoker", fake_invoker)

        try:
            game = runtime.create_game(
                "connect_four",
                config={"run_id": "run-123", "graph_id": "graph-123", "target_app": "WebGoat"},
                player_names={1: "Alpha", 2: "Beta"},
            )
            runtime.make_move(game.game_id, 1, {"column": 0})

            summary_tool = await mcp.get_tool("games_get_dashboard_summary")
            activity_tool = await mcp.get_tool("games_get_game_activity")
            graph_tool = await mcp.get_tool("games_get_game_graph_context")
            views_tool = await mcp.get_tool("games_get_views")

            summary_result = summary_tool.fn()
            activity_result = activity_tool.fn(game_id=game.game_id, limit=10)
            graph_result = graph_tool.fn(game_id=game.game_id, limit=10)
            views_result = views_tool.fn()
            assert summary_result.ok and activity_result.ok and graph_result.ok and views_result.ok
            summary = summary_result.data.model_dump()
            activity = activity_result.data.model_dump()
            graph_context = graph_result.data.model_dump()
            views = views_result.data.views

            assert summary["overview"]["games"] >= 1
            assert summary["overview"]["activity"] >= 1
            assert summary["overview"]["graph_entities"] >= 1
            assert any(item["label"] == "Active" for item in summary["series"])
            row = next(item for item in summary["games"] if item["game_id"] == game.game_id)
            assert row["run_id"] == "run-123"
            assert row["graph_id"] == "graph-123"
            assert row["target_app"] == "WebGoat"
            assert row["activity_count"] >= 1
            assert any(item["event_type"] == "game.move" for item in summary["recent_activity"])
            assert any(item["entity_type"] == "WorkflowRun" for item in summary["related_graph_entities"])
            assert activity["count"] >= 1
            assert any(item["event_type"] == "game.move" for item in activity["entries"])
            assert graph_context["count"] >= 1
            assert any(item["entity_type"] == "WorkflowRun" for item in graph_context["entries"])

            component_ids = [component["id"] for component in views[0]["components"]]
            assert "games-status-mix" in component_ids
            assert "games-sessions" in component_ids
            assert "games-activity-stream" in component_ids
            assert "games-graph-context" in component_ids
        finally:
            set_service("tool_invoker", previous_invoker)