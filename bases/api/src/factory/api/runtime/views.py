"""View registration helper — discovers and registers brick views.

Lazy singleton: runs once on first call, caches result.
Mirrors the dashboard bridge's collect_views() pattern but for the API base.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import make_serializable

logger = logging.getLogger(__name__)

_collected_views: dict[str, dict[str, Any]] | None = None
_views_registered: bool = False


def ensure_views_registered(agg) -> dict[str, dict[str, Any]]:
    """Discover brick views via aggregator, register in ui brick, cache result.

    Safe to call repeatedly — only runs discovery once.
    """
    global _collected_views, _views_registered
    if _collected_views is not None:
        return _collected_views

    if agg is None:
        _collected_views = {}
        return _collected_views

    all_view_defs: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, Any]] = {}

    # Find *_get_views tools across all bricks. If none are visible yet,
    # bricks are still lazy-loading — return without caching so a later
    # /api/health hit retries discovery (else the empty result is cached
    # forever and the dashboard shows 0 views).
    view_tools = [
        tool_name for tool_name in agg.get_all_tool_names()
        if tool_name.endswith("_get_views")
    ]
    if not view_tools:
        logger.warning(
            "No *_get_views tools visible yet — bricks still lazy-loading; "
            "deferring view collection to the next health check"
        )
        return metadata

    for tool_name in view_tools:
        try:
            result = agg.invoke_tool(tool_name)
            # Native MCP v2 tools return a ToolResult envelope
            # ({ok, data: {views: [...]}}); legacy bricks may return a bare
            # list. Same dual-shape unwrap as
            # components/ui/test/factory/ui/test_action_ingestion_real_views.py.
            if isinstance(result, list):
                views = result
            else:
                ok_flag = result.get("ok") if isinstance(result, dict) else getattr(result, "ok", None)
                if ok_flag is False or (isinstance(result, dict) and result.get("error")):
                    error = result.get("error") if isinstance(result, dict) else getattr(result, "error", None)
                    logger.warning(
                        "View payload from %s was rejected: %s",
                        tool_name, error,
                    )
                    continue
                data = result.get("data") if isinstance(result, dict) else getattr(result, "data", None)
                views = getattr(data, "views", None)
                if views is None and isinstance(data, dict):
                    views = data.get("views")
            for vdef in views or []:
                if not isinstance(vdef, dict):
                    vdef = vdef.model_dump(mode="json") if hasattr(vdef, "model_dump") else dict(vdef)
                vid = vdef.get("id")
                if vid:
                    all_view_defs.append(vdef)
                    metadata[vid] = make_serializable(vdef)
        except Exception as e:
            logger.warning("Failed to collect views from %s: %s", tool_name, e)

    _register_views_in_ui(agg, all_view_defs)
    _collected_views = metadata
    logger.info("Collected %d views from %d bricks", len(metadata), len(all_view_defs))
    return metadata


def _register_views_in_ui(agg, view_defs: list[dict[str, Any]]) -> None:
    """Register collected views in the ui brick's ViewManager."""
    global _views_registered
    if not view_defs:
        return
    all_names = agg.get_all_tool_names()
    reg_tool = next((n for n in all_names if n.endswith("register_brick_views")), None)
    if reg_tool is None:
        logger.debug("No register_brick_views tool found — ui brick not loaded?")
        return
    try:
        result = agg.invoke_tool(reg_tool, views=view_defs)
        # ui_register_brick_views returns a ToolResult envelope; the count
        # lives in data (dict or pydantic DTO).
        data = result.get("data") if isinstance(result, dict) else getattr(result, "data", None)
        count = (data.get("count") if isinstance(data, dict) else getattr(data, "count", 0)) or 0
        if count > 0:
            _views_registered = True
        logger.info("Registered %d views in ui brick ViewManager", count)
    except Exception as e:
        logger.warning("Failed to register views in ui brick: %s", e)


def invalidate_view_cache() -> None:
    """Reset cached views (e.g. after brick reload)."""
    global _collected_views, _views_registered
    _collected_views = None
    _views_registered = False
