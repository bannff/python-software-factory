"""Real gateway integration tests for the typed ui_dispatch_action boundary.

bd:python-factory-736 (mechanical consolidation track) retired the REST
bridge (``POST /api/tools/{tool_name}``) these tests previously drove
through. ``ui_dispatch_action`` is invoked directly as a registered MCP
tool now — same real ``cache`` brick tools underneath, no HTTP hop.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def dispatch():
    """Register ui_dispatch_action on a real ToolCatalog instance and return
    the underlying Python callable so tests can invoke it directly,
    mirroring how ``ag_ui_routes.py``/other in-process callers use MCP
    tools without going through an HTTP transport.

    Warms the ``tool_invoker`` service the same way the old REST-bridge
    test did implicitly (``register_bridge_routes`` + a real request):
    ``_get_aggregator()`` is what actually calls ``set_service(
    "tool_invoker", ...)`` as a side effect.
    """
    import asyncio
    from factory.api.runtime.bridge import _get_aggregator
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    from factory.ui.mcp.action_dispatch import register

    _get_aggregator()
    mcp = ToolCatalog("test")
    register(mcp, get_runtime=lambda: None)
    tool = asyncio.run(mcp.get_tool("ui_dispatch_action"))
    return tool.fn


def _dispatch(dispatch, action, args=None, **kwargs):
    """Call ui_dispatch_action directly and return its outer ToolResult
    envelope (schema_version/ok/data/...), matching what the old REST
    test unwrapped from ``response.json()["result"]``."""
    import asyncio

    result = dispatch(action=action, args=args, **kwargs)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    envelope = result.model_dump() if hasattr(result, "model_dump") else result
    assert envelope["schema_version"] == "v1"
    return envelope


def _data(envelope):
    assert envelope["ok"] is True, envelope
    return envelope["data"]


def test_dispatch_fires_a_real_brick_tool(dispatch):
    outcome = _data(_dispatch(dispatch, {"brick": "cache", "tool": "cache_health_check"}))
    assert outcome["ok"] is True
    assert outcome["tool"] == "cache_health_check"
    # outcome["result"] is the raw tool ToolResult envelope, not the
    # unwrapped brick data — ui_dispatch_action passes it through verbatim.
    assert outcome["result"]["data"]["healthy"] is True


def test_dispatch_round_trips_real_arguments(dispatch):
    key = "bd-3jcls3-dispatch-probe"
    _data(_dispatch(dispatch, {"brick": "cache", "tool": "cache_cache_set"},
                    {"key": key, "value": "fired"}))
    outcome = _data(_dispatch(dispatch, {"brick": "cache", "tool": "cache_cache_get"},
                             {"key": key}))
    assert outcome["result"]["data"]["found"] is True
    assert outcome["result"]["data"]["value"] == "fired"


def test_legacy_double_prefixed_name_resolves(dispatch):
    outcome = _data(_dispatch(dispatch, {"brick": "cache", "tool": "cache_cache_get"},
                             {"key": "nope"}))
    assert outcome["tool"] == "cache_get"


def test_unknown_target_is_a_normal_action_outcome(dispatch):
    outcome = _data(_dispatch(dispatch, {"brick": "cache", "tool": "cache_definitely_not_a_tool"}))
    assert outcome["ok"] is False
    assert "unknown tool" in outcome["error"]


@pytest.mark.parametrize("forbidden", ["url", "href", "method", "endpoint"])
def test_non_mcp_target_is_normal_action_outcome(dispatch, forbidden):
    outcome = _data(_dispatch(
        dispatch, {"brick": "cache", "tool": "cache_health_check", forbidden: "/api/evil"},
    ))
    assert outcome["ok"] is False
    assert forbidden in outcome["error"]


def test_target_validation_error_is_a_normal_action_outcome(dispatch):
    """The gateway returns a target error result; dispatch preserves it as data."""
    outcome = _data(_dispatch(
        dispatch, {"brick": "cache", "tool": "cache_cache_get"}, {"bogus_param": 1},
    ))
    assert outcome["ok"] is False
    assert outcome["error"]


def test_human_caller_hint_is_scoped_to_dispatch(dispatch, monkeypatch):
    from factory.mcp_utils import registry
    from factory.mcp_utils.interface import get_caller_hint, get_service

    seen: list[str | None] = []
    real_invoker = get_service("tool_invoker")

    def spy(name, **kwargs):
        seen.append(get_caller_hint())
        return real_invoker(name, **kwargs)

    monkeypatch.setitem(registry._services, "tool_invoker", spy)
    _data(_dispatch(dispatch, {"brick": "cache", "tool": "cache_health_check"},
                    principal_id="wdaniero"))
    assert seen == ["human:wdaniero"]
    assert get_caller_hint() is None


def test_invalidates_stays_inside_the_action_outcome(dispatch):
    outcome = _data(_dispatch(
        dispatch, {"brick": "cache", "tool": "cache_health_check",
                   "invalidates": ["cache_cache_stats"]},
    ))
    assert outcome["invalidates"] == ["cache_cache_stats"]
    assert "components" not in outcome and "views" not in outcome
