"""SVG icons and skeleton markup for HTMX renderers.

Uses the Heroicons registry (324 icons, MIT license) for all icon needs.
Skeleton markup for loading states is defined here directly.
"""

from .heroicons import heroicon

# -- Alert severity icons (mapped to Heroicons names) ----------------------

_ALERT_MAP = {
    "info": "information-circle",
    "success": "check-circle",
    "warning": "exclamation-triangle",
    "error": "x-circle",
}

ALERT_SVG = {
    k: heroicon(v, "stroke-current shrink-0 w-6 h-6")
    for k, v in _ALERT_MAP.items()
}

# -- Stat-figure icons (mapped to Heroicons names) -------------------------

_STAT_MAP = {
    "default": "bolt",
    "chart": "chart-bar",
    "list": "bars-4",
    "document": "document-text",
    "users": "users",
}


def stat_icon(name: str) -> str:
    """Return a stat-figure SVG for the given name.

    Accepts either a legacy alias (chart, list, document, users)
    or any Heroicons name (shield-check, globe-alt, etc.).
    Falls back to the bolt icon.
    """
    hero_name = _STAT_MAP.get(name, name)
    return heroicon(hero_name, "inline-block w-8 h-8 stroke-current")


# Keep STAT_SVG for backward compat — renderers that index it directly
STAT_SVG = {k: stat_icon(k) for k in _STAT_MAP}


# -- Skeleton markup for loading states ------------------------------------

SKELETON = {
    "card": (
        '<div class="flex flex-col gap-4 w-full" id="comp-{cid}">'
        '<div class="skeleton h-32 w-full"></div>'
        '<div class="skeleton h-4 w-28"></div>'
        '<div class="skeleton h-4 w-full"></div></div>'
    ),
    "metric": (
        '<div class="stat" id="comp-{cid}">'
        '<div class="skeleton h-4 w-20 mb-2"></div>'
        '<div class="skeleton h-8 w-16 mb-1"></div>'
        '<div class="skeleton h-3 w-24"></div></div>'
    ),
    "table": (
        '<div class="flex flex-col gap-4 w-full" id="comp-{cid}">'
        '<div class="skeleton h-4 w-full"></div>'
        '<div class="skeleton h-4 w-full"></div>'
        '<div class="skeleton h-4 w-3/4"></div></div>'
    ),
    "text": (
        '<div class="flex flex-col gap-2" id="comp-{cid}">'
        '<div class="skeleton h-4 w-full"></div>'
        '<div class="skeleton h-4 w-3/4"></div></div>'
    ),
}
