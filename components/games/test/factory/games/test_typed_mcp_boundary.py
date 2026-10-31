"""Strict Pydantic-v2 ingress and ToolResult egress for all Games tools."""
from __future__ import annotations

import asyncio
from inspect import signature

import pytest
from factory.games.runtime.runtime import GamesRuntime
from factory.games.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult


EXPECTED_DETERMINISTIC = {
    "get_capabilities", "health_check", "describe_config_schema", "games_get_state",
    "games_legal_moves", "games_evaluate", "games_list", "games_get_dashboard_summary",
    "games_get_game_activity", "games_get_game_graph_context", "games_get_views",
}
EXPECTED_OPERATIONAL = {
    "games_create", "games_move", "games_delete", "games_reset", "games_ctf_move",
    "games_security_move", "games_process_finished", "games_process_workflow_rl",
    "games_write_experiment_report",
}


def _tools(mcp):
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}


def test_catalog_and_all_games_tools_have_strict_same_brick_contracts() -> None:
    tools = _tools(create_mcp_server(GamesRuntime({"store_backend": "memory"})))
    assert set(tools) == EXPECTED_DETERMINISTIC | EXPECTED_OPERATIONAL
    assert sum(tool.fn._mcp_category == "deterministic" for tool in tools.values()) == 11
    assert sum(tool.fn._mcp_category == "operational" for tool in tools.values()) == 9
    for name, tool in tools.items():
        input_model = getattr(tool.fn, "_mcp_input_model", None)
        output_model = getattr(tool.fn, "_mcp_output_model", None)
        assert input_model and output_model, name
        assert input_model.__module__.startswith("factory.games.mcp.contracts"), name
        assert output_model.__module__.startswith("factory.games.mcp.contracts"), name
        assert input_model.model_config.get("extra") == "forbid", name
        assert input_model.model_config.get("strict") is True, name
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"
    assert signature(tools["games_process_workflow_rl"].fn).parameters["match_on"].default is None


def test_envelope_preserves_normal_negative_state() -> None:
    mcp = create_mcp_server(GamesRuntime({"store_backend": "memory"}))
    result = asyncio.run(mcp.get_tool("games_get_state")).fn(game_id="missing")
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.error == "Game missing not found"
    with pytest.raises(Exception):
        asyncio.run(mcp.get_tool("games_get_state")).fn(game_id="missing", unexpected=True)


def test_workflow_rl_forwards_match_on_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    from factory.games.runtime import workflow_rl

    seen: dict[str, object] = {}
    monkeypatch.setattr(workflow_rl, "process_workflow_rl", lambda **kwargs: seen.update(kwargs) or {"ok": True})
    tool = asyncio.run(create_mcp_server(GamesRuntime()).get_tool("games_process_workflow_rl")).fn
    result = tool(graph_id="graph", run_id="run", match_on=["cwe", "file"])
    assert result.ok and result.data.root == {"ok": True}
    assert seen["match_on"] == ["cwe", "file"]


def test_create_returns_a_typed_json_safe_envelope() -> None:
    mcp = create_mcp_server(GamesRuntime({"store_backend": "memory"}))
    result = asyncio.run(mcp.get_tool("games_create")).fn(config={"target_app": "WebGoat"})
    assert result.ok and result.data.game_type == "connect_four"
    assert result.data.config["target_app"] == "WebGoat"


def test_create_with_unknown_game_type_is_a_successful_domain_negative_envelope() -> None:
    mcp = create_mcp_server(GamesRuntime({"store_backend": "memory"}))
    result = asyncio.run(mcp.get_tool("games_create")).fn(game_type="not_a_real_game")
    assert isinstance(result, ToolResult) and result.ok
    assert result.data.error == "unknown_game_type"
    assert result.data.game_type == "not_a_real_game"
    assert result.data.available == GamesRuntime.available_game_types()
    assert "connect_four" in result.data.available
