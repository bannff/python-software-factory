"""Strict Pydantic-v2 ingress and ToolResult egress for all Events tools."""
from __future__ import annotations

import asyncio
import json
from inspect import signature

import pytest
from factory.events.runtime.runtime import EventsRuntime
from factory.events.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult, make_serializable


EXPECTED = {
    "events_get_capabilities", "events_health_check", "events_describe_config_schema",
    "events_get_subscription_registry", "events_query_events", "events_publish",
    "events_publish_projection", "events_score_dev_loop_cycle",
    "events_publish_learning_signal",
    "events_get_event", "events_list_events", "events_replay", "events_list_history",
    "events_query_history", "events_prune_history", "events_authoring_get_status",
    "events_authoring_validate_subscriptions", "events_authoring_upsert_subscription",
    "events_authoring_delete_subscription", "events_get_dashboard_summary",
    "events_get_event_history_entry", "events_get_event_graph_context", "events_get_views",
}


def _tools(mcp):
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}


def test_all_registered_events_tools_have_strict_same_brick_contracts(tmp_path) -> None:
    tools = _tools(create_mcp_server(EventsRuntime(tmp_path)))
    assert set(tools) == EXPECTED
    for name, tool in tools.items():
        fn = tool.fn
        input_model = getattr(fn, "_mcp_input_model", None)
        output_model = getattr(fn, "_mcp_output_model", None)
        assert input_model and output_model, name
        assert input_model.__module__.startswith("factory.events.mcp.contracts"), name
        assert output_model.__module__.startswith("factory.events.mcp.contracts"), name
        assert input_model.model_config["extra"] == "forbid", name
        assert str(signature(fn).return_annotation) == f"ToolResult[{output_model.__name__}]", name


def test_envelopes_preserve_normal_negative_semantics_and_json_safety(tmp_path) -> None:
    mcp = create_mcp_server(EventsRuntime(tmp_path))
    get_event = asyncio.run(mcp.get_tool("events_get_event")).fn
    replay = asyncio.run(mcp.get_tool("events_replay")).fn
    views = asyncio.run(mcp.get_tool("events_get_views")).fn
    missing = get_event(event_id="missing")
    absent_replay = replay(event_id="missing")
    result = views()
    assert isinstance(missing, ToolResult) and missing.ok and missing.data.found is False
    assert absent_replay.ok and absent_replay.data.ok is False
    assert result.ok and result.data.views[0]["id"] == "events-stream"
    with pytest.raises(Exception):
        get_event(event_id="missing", unexpected=True)


def test_views_boolean_color_keys_serialize_lowercase(tmp_path) -> None:
    """Regression: bool colour keys shipped as 'True'/'False', but the renderer's
    ``Record<string, string>`` lookup is case-exact, so it always missed (#46)."""
    mcp = create_mcp_server(EventsRuntime(tmp_path))
    views = asyncio.run(mcp.get_tool("events_get_views")).fn
    result = views()
    assert result.ok

    # Serialize exactly as the transport does: make_serializable stringifies keys.
    payload = json.loads(json.dumps(make_serializable(result.data.model_dump())))
    colors = next(
        component["props"]["filters"]["colors"]
        for component in payload["views"][0]["components"]
        if component["id"] == "events-subscriptions"
    )
    assert colors == {"true": "emerald", "false": "gray"}
    # The lookup is case-exact; booleans serialize as the lowercase strings.
    assert str(True).lower() in colors
    assert str(False).lower() in colors
