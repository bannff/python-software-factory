"""Full-server strict Pydantic v2 MCP contract tests for Cache."""
from __future__ import annotations

import asyncio

from factory.cache.runtime.runtime import CacheRuntime
from factory.cache.server import create_mcp_server


_DETERMINISTIC = {
    "get_capabilities", "health_check", "describe_config_schema", "cache_get_views",
}
_OPERATIONAL = {
    "cache_get", "cache_set", "cache_delete", "cache_keys", "cache_stats",
    "cache_clear", "cache_exists", "cache_ttl",
}


def _server() -> tuple[CacheRuntime, object]:
    runtime = CacheRuntime()
    runtime.get_cache("memory")
    return runtime, create_mcp_server(runtime)


def _call(server: object, name: str, arguments: dict[str, object] | None = None):
    return asyncio.run(server.call_tool(name, arguments or {}))


def _envelope(result: object) -> dict[str, object]:
    assert result.is_error is False
    envelope = result.structured_content
    assert envelope is not None
    assert envelope["schema_version"] == "v1"
    assert envelope["error"] is None
    return envelope


def test_full_server_catalog_and_categories_are_exact() -> None:
    _, server = _server()
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert set(tools) == _DETERMINISTIC | _OPERATIONAL
    assert {name for name, tool in tools.items() if tool.fn._mcp_category == "deterministic"} == _DETERMINISTIC
    assert {name for name, tool in tools.items() if tool.fn._mcp_category == "operational"} == _OPERATIONAL


def test_all_tools_publish_success_envelopes_and_preserve_defaults() -> None:
    _, server = _server()
    calls = {
        "get_capabilities": {}, "health_check": {}, "describe_config_schema": {},
        "cache_get_views": {}, "cache_get": {"key": "missing"},
        "cache_set": {"key": "saved", "value": "value"}, "cache_delete": {"key": "missing"},
        "cache_keys": {}, "cache_stats": {}, "cache_clear": {},
        "cache_exists": {"key": "missing"}, "cache_ttl": {"key": "missing"},
    }
    for name, arguments in calls.items():
        envelope = _envelope(_call(server, name, arguments))
        assert envelope["ok"] is True, name
    assert _envelope(_call(server, "cache_set", {"key": "none", "value": "v"}))["data"]["ttl"] is None
    assert _envelope(_call(server, "cache_keys"))["data"]["pattern"] == "*"



def test_normal_negative_outcomes_are_successful_typed_data() -> None:
    _, server = _server()
    assert _envelope(_call(server, "cache_get", {"key": "missing"}))["data"] == {
        "key": "missing", "value": None, "found": False,
    }
    assert _envelope(_call(server, "cache_delete", {"key": "missing"}))["data"] == {
        "key": "missing", "deleted": False,
    }
    assert _envelope(_call(server, "cache_ttl", {"key": "missing"}))["data"] == {
        "key": "missing", "ttl_seconds": None, "has_ttl": False,
    }
    assert _envelope(_call(server, "cache_clear"))["data"] == {"cleared": 0}
    assert _envelope(_call(server, "cache_keys"))["data"] == {"pattern": "*", "keys": [], "count": 0}


def test_non_string_runtime_value_returns_controlled_failure() -> None:
    runtime, server = _server()
    runtime.get_cache().set("number", 7)
    result = _call(server, "cache_get", {"key": "number"})
    assert result.is_error is True
    assert result.structured_content == {
        "schema_version": "v1", "ok": False, "data": None,
        "error": "tool_execution_failed", "idempotency_key": None,
    }


def test_config_schema_and_view_payload_identifiers_are_preserved() -> None:
    _, server = _server()
    config = _envelope(_call(server, "describe_config_schema"))["data"]
    assert config["type"] == "object"
    assert set(config["properties"]) == {"backend", "url", "max_size", "prefix"}
    assert config["properties"]["backend"]["enum"] == ["memory", "redis"]

    views = _envelope(_call(server, "cache_get_views"))["data"]["views"]
    assert views[0]["id"] == "cache-dashboard"
    page = views[0]["components"][0]
    assert page["id"] == "cache-page"
    assert page["children"][0]["props"]["data_tool"] == "cache_health_check"
    assert page["children"][2]["props"]["tool"] == "cache_cache_get"
    assert [tab["lazy_tool"] for tab in page["children"][3]["props"]["tabs"]] == [
        "cache_cache_keys", "cache_cache_stats", "cache_health_check",
    ]
    assert [action["tool"] for action in page["children"][4]["props"]["actions"]] == [
        "cache_cache_set", "cache_cache_delete", "cache_cache_exists", "cache_cache_ttl", "cache_cache_clear",
    ]
