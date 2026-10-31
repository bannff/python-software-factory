"""Heroicons icon registry — public API.

Provides ``heroicon(name, cls)`` to render any of the ~292 Heroicons
24×24 outline icons as an inline SVG string.  Path data is split across
three generated modules (heroicons_data_{a,d,m}) to keep every file
under 200 lines.

Usage::

    from factory.ui.runtime.adapters.heroicons import heroicon, heroicon_names

    svg = heroicon("shield-check")
    svg = heroicon("bolt", cls="w-4 h-4 text-yellow-400")
    names = heroicon_names()
"""
from __future__ import annotations

from .heroicons_data_a import (
    ICONS as _ICONS_A,
)
from .heroicons_data_d import (
    ICONS as _ICONS_D,
)
from .heroicons_data_m import (
    ICONS as _ICONS_M,
)

# Merge all chunks into a single registry
_REGISTRY: dict[str, list[str]] = {**_ICONS_A, **_ICONS_D, **_ICONS_M}

_SVG_OPEN = (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none"'
    ' viewBox="0 0 24 24" stroke-width="1.5"'
    ' stroke="currentColor" class="{cls}">'
)
_PATH_TPL = (
    '<path stroke-linecap="round" stroke-linejoin="round" d="{d}" />'
)
_SVG_CLOSE = "</svg>"

_FALLBACK = "bolt"


def heroicon(name: str, cls: str = "w-6 h-6") -> str:
    """Return an SVG string for the named Heroicon.

    Falls back to the *bolt* icon when *name* is not found.
    """
    paths = _REGISTRY.get(name) or _REGISTRY.get(_FALLBACK, [])
    inner = "".join(_PATH_TPL.format(d=d) for d in paths)
    return f"{_SVG_OPEN.format(cls=cls)}{inner}{_SVG_CLOSE}"


def heroicon_names() -> list[str]:
    """Return a sorted list of all available icon names."""
    return sorted(_REGISTRY)


# Convenience constant — small info-circle for tooltip triggers.
TOOLTIP_ICON: str = heroicon("information-circle", cls="w-4 h-4 inline")
