"""Health result renderer for HTMX adapter.

Renders health-shaped tool responses (dicts with 'healthy' key) as
prominent status badges with collapsible detail tables.

Strips Python object IDs from backend identifiers and formats
nested health dicts as clean tables instead of raw JSON.

Split from htmx_renderers_result.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any

from .htmx_renderers_html import cell


def format_health(d: dict[str, Any]) -> str:
    """Render health data with prominent status badge + collapsible details."""
    ok = d["healthy"]
    badge_cls = "badge-success" if ok else "badge-error"
    badge_txt = "Healthy" if ok else "Unhealthy"
    icon = "✓" if ok else "✗"

    details = {k: v for k, v in d.items() if k != "healthy"}
    detail_html = ""
    if details:
        scalar = {k: v for k, v in details.items()
                  if isinstance(v, (str, int, float, bool, type(None)))}
        nested = {k: v for k, v in details.items() if k not in scalar}
        rows = "".join(
            f'<tr><td class="text-xs font-medium">{k}</td>'
            f'<td class="text-xs">{cell(v)}</td></tr>'
            for k, v in scalar.items()
        )
        tbl = (f'<table class="table table-sm"><tbody>{rows}</tbody></table>'
               if rows else "")
        nested_html = ""
        for k, v in nested.items():
            nested_html += _format_nested(k, v)
        detail_html = (
            f'<div class="collapse collapse-arrow bg-base-200/50 mt-2">'
            f'<input type="checkbox" />'
            f'<div class="collapse-title text-xs py-2">Details</div>'
            f'<div class="collapse-content">{tbl}{nested_html}</div></div>'
        )

    return (
        f'<div class="flex flex-col items-center gap-2 py-4">'
        f'<span class="text-3xl">{icon}</span>'
        f'<span class="badge {badge_cls} badge-lg gap-1">{badge_txt}</span>'
        f'{detail_html}</div>'
    )


def _format_nested(key: str, val: Any) -> str:
    """Format nested health details as clean tables instead of raw JSON.

    Strips Python object IDs from dict keys (e.g. 'memory:133146708735736'
    becomes 'memory') and renders sub-dicts as readable rows.
    """
    if isinstance(val, dict):
        rows = ""
        for sub_key, sub_val in val.items():
            clean_key = _strip_object_id(sub_key)
            if isinstance(sub_val, dict):
                cells = " · ".join(
                    f'<span class="text-xs">{sk}: {cell(sv)}</span>'
                    for sk, sv in sub_val.items()
                )
                rows += (f'<tr><td class="text-xs font-medium">'
                         f'{clean_key}</td><td>{cells}</td></tr>')
            else:
                rows += (f'<tr><td class="text-xs font-medium">'
                         f'{clean_key}</td>'
                         f'<td class="text-xs">{cell(sub_val)}</td></tr>')
        return (f'<div class="mt-2"><div class="text-xs font-semibold'
                f' text-base-content/60 mb-1">{key}</div>'
                f'<table class="table table-sm">'
                f'<tbody>{rows}</tbody></table></div>')
    return f'<div class="text-xs mt-1">{key}: {cell(val)}</div>'


def _strip_object_id(key: str) -> str:
    """Strip Python object IDs from keys like 'memory:133146708735736'."""
    if ":" in key:
        parts = key.split(":")
        try:
            if len(parts[-1]) > 8 and int(parts[-1]):
                return ":".join(parts[:-1])
        except ValueError:
            pass
    return key
