"""HTMX renderers for tree_view and live_feed components.

tree_view: Collapsible nested data viewer (recursive HTML details).
live_feed: SSE-powered real-time feed using HTMX sse extension.

Split from htmx_renderers_interactive.py to stay under 200 LOC.
"""

from __future__ import annotations

import json
from typing import Any

from ..models import UIComponent
from .heroicons import heroicon


def render_tree_view(c: UIComponent) -> str:
    """Collapsible nested data viewer using HTML details elements."""
    data = c.props.get("data", {})
    title = c.props.get("title", "")
    max_h = c.props.get("max_height", "max-h-[32rem]")
    if not data:
        tool = c.props.get("data_tool", "")
        hx = (
            f' hx-get="/api/tools/{tool}" hx-trigger="load"'
            f' hx-swap="innerHTML"' if tool else ""
        )
        return (
            f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
            f'<div class="card-body">{_title_h(title)}'
            f'<div class="text-center py-4 text-base-content/50"{hx}>'
            f'No data</div></div></div>'
        )
    tree_html = _render_node(data, depth=0)
    return (
        f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
        f'<div class="card-body">{_title_h(title)}'
        f'<div class="{max_h} overflow-auto">{tree_html}'
        f'</div></div></div>'
    )


def render_live_feed(c: UIComponent) -> str:
    """SSE-powered real-time feed using HTMX sse extension."""
    sse_url = c.props.get("sse_url", "")
    title = c.props.get("title", "")
    max_items = c.props.get("max_items", 50)
    event_name = c.props.get("event_name", "message")
    icon = heroicon("signal", "w-4 h-4 text-success animate-pulse")
    if not sse_url:
        return (
            f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
            f'<div class="card-body">{_title_h(title)}'
            f'<div class="text-center py-4 text-base-content/50">'
            f'No SSE endpoint configured</div></div></div>'
        )
    return (
        f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
        f'<div class="card-body">'
        f'<div class="flex items-center gap-2">'
        f'{_title_h(title)}{icon}</div>'
        f'<div hx-ext="sse" sse-connect="{sse_url}"'
        f' class="max-h-96 overflow-y-auto flex flex-col-reverse">'
        f'<div sse-swap="{event_name}" hx-swap="afterbegin"'
        f' x-data="{{items:0}}"'
        f' x-init="$watch(\'$el.children.length\', v => {{'
        f' if(v>{max_items}) $el.lastChild.remove() }})">'
        f'</div></div></div></div>'
    )


# ── Helpers ──────────────────────────────────────────────

def _title_h(title: str) -> str:
    return f'<h3 class="card-title text-sm mb-2">{title}</h3>' if title else ""


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _render_node(data: Any, depth: int = 0) -> str:
    """Recursively render data as collapsible tree nodes."""
    indent = f"ml-{min(depth * 4, 16)}"
    if isinstance(data, dict):
        if not data:
            return '<span class="text-base-content/40 text-xs">{}</span>'
        parts = []
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                inner = _render_node(v, depth + 1)
                badge = (f"{len(v)} items" if isinstance(v, list)
                         else f"{len(v)} keys")
                parts.append(
                    f'<details class="{indent}" open>'
                    f'<summary class="cursor-pointer py-1 text-sm'
                    f' hover:text-primary transition-colors">'
                    f'<span class="font-medium">{k}</span>'
                    f' <span class="badge badge-ghost badge-xs">'
                    f'{badge}</span></summary>'
                    f'<div class="border-l border-base-300 ml-2">'
                    f'{inner}</div></details>'
                )
            else:
                parts.append(
                    f'<div class="{indent} flex gap-2 py-1 text-sm">'
                    f'<span class="text-base-content/60">{k}:</span>'
                    f'<span class="font-medium">{_leaf(v)}</span></div>'
                )
        return "".join(parts)
    if isinstance(data, list):
        if not data:
            return '<span class="text-base-content/40 text-xs">[]</span>'
        parts = []
        for i, item in enumerate(data[:100]):
            if isinstance(item, (dict, list)) and item:
                inner = _render_node(item, depth + 1)
                parts.append(
                    f'<details class="{indent}">'
                    f'<summary class="cursor-pointer py-1 text-sm'
                    f' hover:text-primary transition-colors">[{i}]'
                    f'</summary>'
                    f'<div class="border-l border-base-300 ml-2">'
                    f'{inner}</div></details>'
                )
            else:
                parts.append(
                    f'<div class="{indent} py-1 text-sm">'
                    f'<span class="text-base-content/40">[{i}]</span> '
                    f'{_leaf(item)}</div>'
                )
        return "".join(parts)
    return f'<span class="text-sm">{_leaf(data)}</span>'


def _leaf(v: Any) -> str:
    """Format a leaf value with type-appropriate styling."""
    if v is None:
        return '<span class="text-base-content/30">null</span>'
    if isinstance(v, bool):
        cls = "text-success" if v else "text-error"
        return f'<span class="{cls}">{"true" if v else "false"}</span>'
    if isinstance(v, (int, float)):
        return f'<span class="text-info">{v}</span>'
    if isinstance(v, str):
        s = v[:77] + "…" if len(v) > 80 else v
        return f'<span class="text-warning">"{_escape(s)}"</span>'
    return str(v)
