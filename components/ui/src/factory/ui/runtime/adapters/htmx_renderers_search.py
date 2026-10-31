"""Search result renderer — relevance-scored document cards.

Renders search results as visually rich cards with:
- Result count badge with query context
- Numbered results with relevance radial progress
- Content preview with truncation
- Document ID + source badges
- Staggered fade-in animation per card
- Empty state with search icon

Used by the result renderer when it detects search-shaped data
(list of dicts with 'score' and 'content' keys).
"""

from __future__ import annotations

from .htmx_renderers_html import empty


def is_search_result(rows: list[dict]) -> bool:
    """Detect if rows look like search results (have score + content)."""
    if not rows or not isinstance(rows[0], dict):
        return False
    keys = set(rows[0].keys())
    return "score" in keys and "content" in keys


def render_search_results(rows: list[dict], extra: dict | None = None) -> str:
    """Render search results as relevance-scored document cards."""
    if not rows:
        return _empty_search()

    total = extra.get("total", len(rows)) if extra else len(rows)
    header = (
        f'<div class="flex items-center gap-3 mb-4">'
        f'<div class="badge badge-primary gap-1">'
        f'<svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3"'
        f' fill="none" viewBox="0 0 24 24" stroke="currentColor">'
        f'<path stroke-linecap="round" stroke-linejoin="round"'
        f' stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14'
        f' 0 7 7 0 0114 0z"/></svg>'
        f'{total} result{"s" if total != 1 else ""}</div>'
        f'</div>'
    )
    cards = "".join(_result_card(r, i) for i, r in enumerate(rows))
    return f'<div class="space-y-3">{header}{cards}</div>'


def _result_card(row: dict, index: int) -> str:
    """Render a single search result as a card with relevance indicator."""
    doc_id = row.get("document_id", row.get("id", ""))
    content = row.get("content", "")
    score = row.get("score", 0)
    source = row.get("source", "")

    preview = content[:300].rstrip()
    if len(content) > 300:
        preview += "…"

    pct = min(100, max(0, round(float(score) * 100)))
    color = _score_color(pct)
    delay = index * 80

    # Rank number
    rank = f'<span class="text-lg font-bold text-base-content/20">#{index + 1}</span>'

    # Source badge
    src_h = (
        f'<span class="badge badge-outline badge-xs gap-1">'
        f'<svg xmlns="http://www.w3.org/2000/svg" class="w-2.5 h-2.5"'
        f' fill="none" viewBox="0 0 24 24" stroke="currentColor">'
        f'<path stroke-linecap="round" stroke-linejoin="round"'
        f' stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1'
        f' 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586'
        f' 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>'
        f'{source}</span>'
    ) if source else ""

    # Radial relevance indicator
    radial = (
        f'<div class="radial-progress {color} text-xs"'
        f' style="--value:{pct};--size:2.5rem;--thickness:3px"'
        f' role="progressbar">{pct}%</div>'
    )

    return (
        f'<div class="card bg-base-100 shadow-sm border border-base-200'
        f' hover:shadow-md hover:border-primary/20 transition-all'
        f' duration-200" style="animation:fadeIn .35s ease-out'
        f' {delay}ms both">'
        f'<div class="card-body p-4">'
        f'<div class="flex gap-4">'
        f'<div class="flex flex-col items-center gap-1 pt-1">'
        f'{rank}{radial}</div>'
        f'<div class="flex-1 min-w-0">'
        f'<div class="flex items-center gap-2 mb-2">'
        f'<span class="font-mono text-xs px-2 py-0.5 bg-base-200'
        f' rounded text-base-content/60">{_escape(doc_id)}</span>'
        f'{src_h}</div>'
        f'<p class="text-sm text-base-content/80 leading-relaxed">'
        f'{_escape(preview)}</p>'
        f'</div></div></div></div>'
    )


def _empty_search() -> str:
    """Render a styled empty state for no search results."""
    return (
        '<div class="flex flex-col items-center justify-center py-12 gap-3">'
        '<svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16'
        ' text-base-content/15" fill="none" viewBox="0 0 24 24"'
        ' stroke="currentColor"><path stroke-linecap="round"'
        ' stroke-linejoin="round" stroke-width="1.5"'
        ' d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>'
        '<p class="text-base-content/50 text-sm">No results found</p>'
        '<p class="text-base-content/30 text-xs">Try a different query'
        ' or broaden your search terms</p></div>'
    )


def _score_color(pct: int) -> str:
    """Map relevance percentage to a DaisyUI color class."""
    if pct >= 70:
        return "text-success"
    if pct >= 40:
        return "text-info"
    if pct >= 20:
        return "text-warning"
    return "text-base-content/30"


def _escape(text: str) -> str:
    """HTML-escape text for safe rendering."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
