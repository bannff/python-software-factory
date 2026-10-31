"""Closed allowlist of frontend Canvas view IDs (authorization surface).

Mirrors the ``CanvasViewId`` union in
``frontends/next-dashboard/lib/types/workbench.ts`` exactly. This is the global
authenticated-canvas allowlist used by ``ui_resolve_canvas`` — an
authorization / existence check for globally-registered views, not
owner-specific content. Parity with the TS source is contract-tested.
"""
from __future__ import annotations

from typing import Literal, get_args

CanvasViewId = Literal[
    "welcome", "graph", "timeline-v2", "findings", "evals", "metrics", "ml",
    "games", "blockchain", "sandbox", "capabilities", "sessions", "schedules", "lessons",
    "artifacts", "crews", "live", "settings",
]

CANVAS_VIEW_IDS: frozenset[str] = frozenset(get_args(CanvasViewId))

__all__ = ["CANVAS_VIEW_IDS", "CanvasViewId"]
