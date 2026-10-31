"""Interactive table renderer with Alpine.js sorting and filtering.

Replaces the basic table in htmx_renderers.py with a richer version
that supports column sorting, client-side search, row count badges,
and proper empty states.

Props:
    columns: list of {key, label} dicts
    rows: list of row dicts
    sortable: bool (default True) — enable click-to-sort headers
    searchable: bool (default False) — show search input
    page_size: int (default 0 = show all) — paginate rows
    title: str — optional card title
    empty_state: {message, hint, icon} — custom empty state
"""

from __future__ import annotations

import json
from typing import Any

from ..models import UIComponent
from .htmx_intent import intent_cls, maybe_collapse
from .htmx_icons import SKELETON


def render_table(c: UIComponent) -> str:
    """Render an interactive table with sorting and filtering."""
    if c.props.get("loading"):
        return SKELETON["table"].format(cid=c.id)
    columns = c.props.get("columns", [])
    rows = c.props.get("rows", [])
    title = c.props.get("title", "")
    sortable = c.props.get("sortable", True)
    searchable = c.props.get("searchable", False)

    if not rows:
        inner = _rich_empty(c) or _card_empty("No data", c)
        return maybe_collapse(c, inner, title)

    # Serialize rows as JSON for Alpine.js
    keys = [col.get("key", "") for col in columns]
    safe_rows = json.dumps(rows[:500], default=str)

    search_h = ""
    if searchable:
        search_h = (
            '<input type="text" x-model="search" placeholder="Filter…"'
            ' class="input input-bordered input-sm w-full max-w-xs'
            ' mb-3 focus:input-primary" />'
        )

    header = "".join(_sort_header(col, sortable) for col in columns)

    row_tpl = "".join(
        f'<td x-text="row.{k}" class="text-sm"></td>'
        if _is_simple_key(k) else
        f'<td class="text-sm">'
        f'<span x-text="row[{json.dumps(k)}]"></span></td>'
        for k in keys
    )

    count_h = (
        '<div class="text-xs text-base-content/50 mt-1 px-1">'
        '<span x-text="filtered.length"></span> result(s)</div>'
    )

    inner = (
        f'<div class="card bg-base-100 shadow-sm {intent_cls(c)}"'
        f' id="comp-{c.id}"'
        f' x-data=\'{_alpine_data(safe_rows, sortable)}\'>'
        f'<div class="card-body">'
        f'{_title_h(title, len(rows))}'
        f'{search_h}'
        f'<div class="overflow-x-auto">'
        f'<table class="table table-zebra table-sm">'
        f'<thead><tr>{header}</tr></thead>'
        f'<tbody>'
        f'<template x-for="row in filtered" :key="JSON.stringify(row)">'
        f'<tr class="hover">{row_tpl}</tr>'
        f'</template>'
        f'</tbody></table></div>'
        f'{count_h}'
        f'</div></div>'
    )
    return maybe_collapse(c, inner, title)


def _sort_header(col: dict, sortable: bool) -> str:
    """Render a sortable column header."""
    key = col.get("key", "")
    label = col.get("label", key)
    if not sortable:
        return f'<th class="bg-base-200">{label}</th>'
    safe_key = json.dumps(key)
    return (
        f'<th class="bg-base-200 cursor-pointer select-none'
        f' hover:bg-base-300 transition-colors"'
        f' @click="sortKey==={safe_key}'
        f' ? sortAsc=!sortAsc : (sortKey={safe_key}, sortAsc=true)">'
        f'<div class="flex items-center gap-1">{label}'
        f'<span class="text-xs opacity-50"'
        f' x-show="sortKey==={safe_key}"'
        f' x-text="sortAsc ? \'↑\' : \'↓\'"></span>'
        f'</div></th>'
    )


def _alpine_data(rows_json: str, sortable: bool) -> str:
    """Build the Alpine.js x-data expression for the table.

    Uses Alpine getter for `filtered` to reactively sort/filter rows.
    """
    return (
        f'{{"allRows":{rows_json},"search":"","sortKey":"","sortAsc":true,'
        f'get filtered(){{ let r=this.allRows;'
        f' if(this.search){{ let s=this.search.toLowerCase();'
        f' r=r.filter(row=>Object.values(row).some('
        f'v=>String(v).toLowerCase().includes(s))) }}'
        f' if(this.sortKey){{ let k=this.sortKey,a=this.sortAsc?1:-1;'
        f' r=[...r].sort((x,y)=>String(x[k]||"")'
        f'.localeCompare(String(y[k]||""),undefined,'
        f'{{numeric:true}})*a) }}'
        f' return r }}'
        f'}}'
    )


def _is_simple_key(key: str) -> bool:
    """Check if key is a valid JS identifier (no dots, spaces, etc.)."""
    return key.isidentifier()


def _title_h(title: str, count: int) -> str:
    """Render card title with row count badge."""
    if not title:
        return ""
    return (
        f'<div class="flex items-center gap-2 mb-2">'
        f'<h3 class="card-title text-sm">{title}</h3>'
        f'<span class="badge badge-ghost badge-sm">{count}</span></div>'
    )


def _rich_empty(c: UIComponent) -> str | None:
    """Render a rich empty state from the empty_state prop."""
    es = c.props.get("empty_state")
    if not es:
        return None
    from .heroicons import heroicon
    msg = es.get("message", "No data yet")
    hint = es.get("hint", "")
    icon = heroicon(
        es.get("icon", "inbox"),
        "w-12 h-12 stroke-current text-base-content/20",
    )
    hint_h = (
        f'<p class="text-xs text-base-content/40 mt-1">{hint}</p>'
        if hint else ""
    )
    return (
        f'<div class="card bg-base-100 shadow-sm flex-1 {intent_cls(c)}"'
        f' id="comp-{c.id}">'
        f'<div class="flex flex-col items-center justify-center'
        f' py-12 gap-2">{icon}'
        f'<p class="text-sm text-base-content/50">{msg}</p>'
        f'{hint_h}</div></div>'
    )


def _card_empty(msg: str, c: UIComponent) -> str:
    return (
        f'<div class="card bg-base-100 shadow-sm flex-1 {intent_cls(c)}"'
        f' id="comp-{c.id}">'
        f'<div class="text-center py-8 text-base-content/50">'
        f'{msg}</div></div>'
    )
