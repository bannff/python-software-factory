"""Tool-invoker plumbing shared by the dashboard readers.

The activity and graph readers both reach into the shared MCP service registry
to call sibling bricks (events, graph) and must normalize the ToolResult
envelope + pydantic payloads the same way. That plumbing lives here so both
readers stay focused on their own query shape.
"""

from __future__ import annotations

from typing import Any


def get_invoker():
    """Return the shared MCP tool invoker, or ``None`` when unavailable."""
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def envelope_data(result: Any) -> dict[str, Any]:
    """Return the ``data`` mapping from a tool_invoker return value.

    The process tool_invoker (``MCPAggregator.invoke_tool``) hands back the
    ToolResult envelope as a plain dict: ``{"ok": bool, "data": {...}, ...}``.
    Tolerate ToolResult-like objects (``.ok``/``.data``) for back-compat, and
    a pydantic ``data`` payload by dumping it to a dict.
    """
    if result is None:
        return {}
    ok = result.get("ok") if isinstance(result, dict) else getattr(result, "ok", False)
    if not ok:
        return {}
    data = result.get("data") if isinstance(result, dict) else getattr(result, "data", None)
    if data is None:
        return {}
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    return data if isinstance(data, dict) else {}


def entity_dict(entity: Any) -> dict[str, Any]:
    """Normalize a graph entity (dict or pydantic model) into a dict."""
    if hasattr(entity, "model_dump"):
        return entity.model_dump(mode="json")
    return entity if isinstance(entity, dict) else {}
