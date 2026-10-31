"""Tool result renderer for HTMX adapter.

Converts MCP tool JSON responses into DaisyUI-styled HTML.
Handles common result shapes: errors, list payloads, flat dicts,
and nested dicts (rendered as collapsible sections instead of raw JSON).

This replaces the dashboard's result_fmt.py — all rendering logic
belongs in the ui brick's adapter layer per clean architecture tenets.
"""

from __future__ import annotations

import json
from typing import Any

from .htmx_renderers_html import (
    alert, cell, dict_table, empty, kv_table, pre,
    simple_list, stats_bar,
)
from .htmx_renderers_search import is_search_result, render_search_results
from .htmx_renderers_health import format_health as _format_health

# Keys that typically hold a list payload in tool responses.
_LIST_KEYS = (
    "results", "events", "documents", "runs", "suites",
    "evaluators", "memories", "blobs", "connections",
    "bricks", "agents", "workflows", "items", "entries",
    "findings", "scans", "sessions", "collections",
)


def format_tool_result(result: Any) -> str:
    """Format a tool result as DaisyUI-styled HTML."""
    if result is None:
        return empty("No result returned.")
    if isinstance(result, str):
        return pre(result)
    if isinstance(result, dict):
        return _format_dict(result)
    if isinstance(result, list):
        return _format_list(result)
    return pre(json.dumps(result, indent=2, default=str))


def _format_dict(d: dict[str, Any]) -> str:
    """Format a dict — detect common patterns."""
    if "error" in d:
        return alert(str(d["error"]), "error")

    # Health-shaped data — prominent status badge first
    if "healthy" in d and isinstance(d["healthy"], bool):
        return _format_health(d)

    # Results with a list payload
    for key in _LIST_KEYS:
        if key in d and isinstance(d[key], list):
            rows = d[key]
            extra = {k: v for k, v in d.items() if k != key}
            # Search results get rich card rendering
            if is_search_result(rows):
                return render_search_results(rows, extra)
            header = stats_bar(extra) if extra else ""
            return header + _format_list(rows)

    # Flat dict (all scalar values) → key-value table
    if all(isinstance(v, (str, int, float, bool, type(None)))
           for v in d.values()):
        return kv_table(d)

    # Nested dict → collapsible sections per key
    return _collapsible_dict(d)


def _collapsible_dict(d: dict[str, Any]) -> str:
    """Render nested dict as collapsible sections per top-level key.

    Scalar values go into a stats bar at the top.
    Dict/list values each get a collapsible DaisyUI collapse panel.
    """
    scalars = {k: v for k, v in d.items()
               if isinstance(v, (str, int, float, bool, type(None)))}
    nested = {k: v for k, v in d.items() if k not in scalars}

    parts: list[str] = []
    if scalars:
        parts.append(stats_bar(scalars))

    for key, val in nested.items():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            content = dict_table(val)
        elif isinstance(val, list):
            content = simple_list(val)
        elif isinstance(val, dict):
            content = _render_nested_dict(val)
        else:
            content = f"<span>{cell(val)}</span>"

        parts.append(
            f'<div class="collapse collapse-arrow bg-base-100'
            f' shadow-sm">'
            f'<input type="checkbox" checked />'
            f'<div class="collapse-title font-medium text-sm">'
            f'{key} <span class="badge badge-ghost badge-sm ml-2">'
            f'{_badge_hint(val)}</span></div>'
            f'<div class="collapse-content">{content}</div></div>'
        )

    return "\n".join(parts) if parts else empty("Empty result.")


def _badge_hint(val: Any) -> str:
    """Short type hint for collapse badge."""
    if isinstance(val, list):
        return f"{len(val)} items"
    if isinstance(val, dict):
        return f"{len(val)} keys"
    return type(val).__name__


def _render_nested_dict(d: dict[str, Any]) -> str:
    """Render a nested dict as a kv_table, flattening sub-dicts inline."""
    flat: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            if not v:
                flat[k] = "(empty)"
            else:
                for sk, sv in v.items():
                    flat[f"{k}.{sk}"] = sv
        else:
            flat[k] = v
    return kv_table(flat)


def _format_list(items: list) -> str:
    """Format a list as a DaisyUI table or simple list."""
    if not items:
        return empty("No items found.")
    if isinstance(items[0], dict):
        return dict_table(items)
    return simple_list(items)


