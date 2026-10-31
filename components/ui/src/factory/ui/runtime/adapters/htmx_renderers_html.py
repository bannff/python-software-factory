"""Shared HTML primitives for HTMX result renderers.

Low-level helpers for rendering tables, stats bars, cells, alerts,
and empty states. Used by htmx_renderers_result.py and potentially
other result formatters.

Split from htmx_renderers_result.py to stay under 200 LOC per file.
"""

from __future__ import annotations

import json
from typing import Any


def dict_table(rows: list[dict]) -> str:
    """Render a list of dicts as a sortable, filterable table."""
    if not rows:
        return empty("No data.")
    import json as _json
    keys = list(rows[0].keys())
    if len(keys) > 8:
        keys = keys[:8]
    safe_rows = _json.dumps(rows[:200], default=str)
    header = "".join(
        f'<th class="bg-base-200 cursor-pointer select-none'
        f' hover:bg-base-300 transition-colors"'
        f' @click="sortKey==={_json.dumps(k)}'
        f' ? sortAsc=!sortAsc : (sortKey={_json.dumps(k)}, sortAsc=true)">'
        f'<div class="flex items-center gap-1">{k}'
        f'<span class="text-xs opacity-50"'
        f' x-show="sortKey==={_json.dumps(k)}"'
        f' x-text="sortAsc ? \'↑\' : \'↓\'"></span></div></th>'
        for k in keys
    )
    row_tpl = "".join(
        f'<td class="text-sm"><span x-text='
        f'"String(row[{_json.dumps(k)}] ?? \'—\')"></span></td>'
        for k in keys
    )
    alpine = (
        f'{{"allRows":{safe_rows},"search":"","sortKey":"","sortAsc":true,'
        f'get filtered(){{ let r=this.allRows;'
        f' if(this.search){{ let s=this.search.toLowerCase();'
        f' r=r.filter(row=>Object.values(row).some('
        f'v=>String(v).toLowerCase().includes(s))) }}'
        f' if(this.sortKey){{ let k=this.sortKey,a=this.sortAsc?1:-1;'
        f' r=[...r].sort((x,y)=>String(x[k]||"")'
        f'.localeCompare(String(y[k]||""),undefined,'
        f'{{numeric:true}})*a) }}'
        f' return r }}}}'
    )
    count = (
        '<div class="text-xs text-base-content/50 mt-1 px-1">'
        '<span x-text="filtered.length"></span> result(s)</div>'
    )
    search = (
        '<input type="text" x-model="search" placeholder="Filter…"'
        ' class="input input-bordered input-sm w-full max-w-xs'
        ' mb-2 focus:input-primary" />'
    ) if len(rows) > 5 else ""
    return (
        f"<div class='card bg-base-100 shadow-sm' x-data='{alpine}'>"
        f'<div class="card-body p-3">{search}'
        f'<div class="overflow-x-auto">'
        f'<table class="table table-zebra table-sm">'
        f'<thead><tr>{header}</tr></thead>'
        f'<tbody>'
        f'<template x-for="row in filtered"'
        f' :key="JSON.stringify(row)">'
        f'<tr class="hover">{row_tpl}</tr>'
        f'</template>'
        f'</tbody></table></div>{count}</div></div>'
    )


def kv_table(d: dict[str, Any]) -> str:
    """Render a flat dict as a key-value table."""
    rows = "".join(
        f'<tr class="hover"><td class="font-medium">{k}</td>'
        f'<td>{cell(v)}</td></tr>'
        for k, v in d.items())
    return (
        f'<div class="card bg-base-100 shadow-sm">'
        f'<div class="overflow-x-auto">'
        f'<table class="table table-sm">'
        f'<thead><tr><th class="bg-base-200">Key</th>'
        f'<th class="bg-base-200">Value</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></div>'
    )


def simple_list(items: list) -> str:
    """Render a list of scalars as a compact list."""
    if not items:
        return empty("Empty list.")
    li = "".join(
        f'<li class="py-1 border-b border-base-200 last:border-0">'
        f'{cell(i)}</li>' for i in items[:100]
    )
    count = (f'<div class="text-xs text-base-content/50 mt-1">'
             f'{len(items)} item(s)</div>')
    return f'<ul class="list-none p-2">{li}</ul>{count}'


def stats_bar(d: dict[str, Any]) -> str:
    """Render scalar fields as a compact stats bar."""
    if not d:
        return ""
    parts = ""
    for k, v in d.items():
        parts += (f'<div class="stat py-2 px-4">'
                  f'<div class="stat-title text-xs">{k}</div>'
                  f'<div class="stat-value text-sm">{cell(v)}</div></div>')
    return f'<div class="stats shadow-sm bg-base-100 mb-3 w-full">{parts}</div>'


def cell(v: Any) -> str:
    """Format a single cell value."""
    if v is None:
        return '<span class="text-base-content/30">—</span>'
    if isinstance(v, bool):
        icon = "✓" if v else "✗"
        cls = "text-success" if v else "text-error"
        return f'<span class="{cls}">{icon}</span>'
    if isinstance(v, float) and 1_000_000_000 < v < 2_000_000_000:
        return _format_epoch(v)
    if isinstance(v, (dict, list)):
        s = json.dumps(v, default=str)
        if len(s) > 80:
            s = s[:77] + "…"
        return f'<code class="text-xs">{s}</code>'
    s = str(v)
    if len(s) > 120:
        s = s[:117] + "…"
    return s


def _format_epoch(ts: float) -> str:
    """Format a Unix epoch timestamp as a human-readable datetime."""
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return (f'<time datetime="{dt.isoformat()}"'
            f' class="text-sm">{dt.strftime("%b %d, %Y %H:%M UTC")}'
            f'</time>')


def pre(text: str) -> str:
    """Render preformatted text block."""
    return (f'<pre class="bg-base-200 p-4 rounded-lg max-h-96'
            f' overflow-auto"><code class="text-sm">{text}</code></pre>')


def empty(msg: str) -> str:
    """Render a styled empty state with icon."""
    return (
        '<div class="flex flex-col items-center justify-center py-8 gap-2">'
        '<svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10'
        ' text-base-content/15" fill="none" viewBox="0 0 24 24"'
        ' stroke="currentColor"><path stroke-linecap="round"'
        ' stroke-linejoin="round" stroke-width="1.5"'
        ' d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247'
        ' 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10'
        ' 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504'
        ' 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375'
        'c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504'
        ' 1.125 1.125 1.125z"/></svg>'
        f'<p class="text-sm text-base-content/40">{msg}</p></div>'
    )


def alert(msg: str, severity: str = "info") -> str:
    """Render a DaisyUI alert."""
    return (f'<div class="alert alert-{severity} shadow-sm">'
            f'<span>{msg}</span></div>')
