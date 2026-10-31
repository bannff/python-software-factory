"""HTMX renderers for interactive component types.

Components: code_block, timeline, stat_grid.
Uses DaisyUI + Alpine.js for rich client-side interactivity.
"""

from __future__ import annotations

from ..models import UIComponent
from .heroicons import heroicon


def render_code_block(c: UIComponent) -> str:
    """Syntax-highlighted code block with copy button."""
    code = c.props.get("code", "")
    lang = c.props.get("language", "")
    title = c.props.get("title", "")
    max_h = c.props.get("max_height", "max-h-96")
    cid = c.id
    title_h = (
        f'<div class="flex justify-between items-center px-4 py-2'
        f' bg-base-300 rounded-t-lg border-b border-base-content/10">'
        f'<span class="text-xs font-mono text-base-content/60">'
        f'{title or lang}</span>'
        f'<button class="btn btn-ghost btn-xs gap-1"'
        f' @click="copied=true; navigator.clipboard.writeText('
        f"document.getElementById('code-{cid}').textContent);"
        f' setTimeout(()=>copied=false, 2000)"'
        f' x-text="copied ? \'Copied!\' : \'Copy\'">'
        f'Copy</button></div>'
    )
    return (
        f'<div class="rounded-lg overflow-hidden bg-base-200'
        f' shadow-sm" id="comp-{cid}" x-data="{{copied:false}}">'
        f'{title_h}'
        f'<pre class="{max_h} overflow-auto p-4 m-0">'
        f'<code id="code-{cid}" class="text-sm font-mono'
        f' whitespace-pre-wrap">{_escape(code)}</code></pre></div>'
    )


def render_timeline(c: UIComponent) -> str:
    """DaisyUI timeline for events, workflow steps, audit logs."""
    events = c.props.get("events", [])
    title = c.props.get("title", "")
    if not events:
        tool = c.props.get("data_tool", "")
        hx = (
            f' hx-get="/api/tools/{tool}" hx-trigger="load"'
            f' hx-swap="innerHTML"' if tool else ""
        )
        icon = heroicon(
            "clock", "w-10 h-10 stroke-current text-base-content/20")
        return (
            f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
            f'<div class="card-body">{_title_h(title)}'
            f'<div class="flex flex-col items-center justify-center'
            f' py-8 gap-2"{hx}>{icon}'
            f'<span class="text-sm text-base-content/50">'
            f'No events yet</span></div></div></div>'
        )
    items_h = ""
    for i, ev in enumerate(events):
        status = ev.get("status", "default")
        icon_name = ev.get("icon", _status_icon(status))
        svg = heroicon(icon_name, f"w-4 h-4 {_status_color(status)}")
        time_h = (
            f'<time class="font-mono text-xs">{ev["time"]}</time>'
            if ev.get("time") else ""
        )
        desc = ev.get("description", "")
        desc_h = (
            f'<p class="text-xs text-base-content/60 mt-0.5">{desc}</p>'
            if desc else ""
        )
        line_cls = "bg-primary" if status == "active" else ""
        hr_open = f'<hr class="{line_cls}" />' if i > 0 else ""
        items_h += (
            f'<li>{hr_open}'
            f'<div class="timeline-start text-xs'
            f' text-base-content/50">{time_h}</div>'
            f'<div class="timeline-middle">{svg}</div>'
            f'<div class="timeline-end timeline-box">'
            f'<span class="font-medium text-sm">'
            f'{ev.get("title", "")}</span>{desc_h}</div>'
            f'<hr class="{line_cls}" /></li>'
        )
    return (
        f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
        f'<div class="card-body">{_title_h(title)}'
        f'<ul class="timeline timeline-vertical timeline-compact">'
        f'{items_h}</ul></div></div>'
    )


def render_stat_grid(c: UIComponent) -> str:
    """Compact grid of key-value pairs for health, config, summaries."""
    items = c.props.get("items", [])
    title = c.props.get("title", "")
    if not items:
        return (
            f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
            f'<div class="card-body">{_title_h(title)}'
            f'<div class="text-center py-4 text-base-content/50">'
            f'No data</div></div></div>'
        )
    rows_h = ""
    for item in items:
        key = item.get("key", "")
        val = item.get("value", "")
        icon_name = item.get("icon", "")
        status = item.get("status", "")
        icon_h = (heroicon(icon_name, "w-4 h-4 text-base-content/40")
                  if icon_name else "")
        val_cls = _status_color(status) if status else ""
        rows_h += (
            f'<div class="flex items-center justify-between py-2 px-3'
            f' border-b border-base-200 last:border-0">'
            f'<div class="flex items-center gap-2">{icon_h}'
            f'<span class="text-sm text-base-content/70">{key}</span>'
            f'</div>'
            f'<span class="text-sm font-medium {val_cls}">{val}</span>'
            f'</div>'
        )
    return (
        f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
        f'<div class="card-body">{_title_h(title)}'
        f'{rows_h}</div></div>'
    )


# ── Shared helpers ───────────────────────────────────────

def _escape(text: str) -> str:
    """HTML-escape text for safe rendering."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _title_h(title: str) -> str:
    return f'<h3 class="card-title text-sm mb-2">{title}</h3>' if title else ""


def _status_icon(status: str) -> str:
    return {
        "success": "check-circle", "error": "x-circle",
        "warning": "exclamation-triangle", "active": "bolt",
        "pending": "clock", "skipped": "minus-circle",
    }.get(status, "ellipsis-horizontal-circle")


def _status_color(status: str) -> str:
    return {
        "success": "text-success", "error": "text-error",
        "warning": "text-warning", "active": "text-primary",
        "healthy": "text-success", "unhealthy": "text-error",
    }.get(status, "")
