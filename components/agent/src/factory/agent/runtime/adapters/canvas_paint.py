"""Lift a ``ui_paint_canvas`` result into a canvas ``state_delta`` event payload.

Shared by every chat runtime: the tool returns a v1 envelope whose ``data``
carries the ``_a2ui_canvas`` sentinel, and the AG-UI mapper turns the
resulting ``state_delta`` into ``STATE_SNAPSHOT`` / ``STATE_DELTA`` so the
canvas views (``agentState.canvas.<slot>``) paint.
"""
from __future__ import annotations

from typing import Any

_CANVAS_TARGETS = frozenset({"graph", "timeline", "findings", "live"})


def canvas_state_delta(payload: Any) -> tuple[str, str, dict[str, Any]] | None:
    """Extract a ``(target, mode, payload)`` canvas paint from a tool result.

    Malformed sentinels return ``None`` — never a stream failure.
    """
    if not isinstance(payload, dict) or payload.get("schema_version") != "v1":
        return None
    if payload.get("ok") is not True or payload.get("error") is not None:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    sentinel = data.get("_a2ui_canvas")
    if not isinstance(sentinel, dict):
        return None
    target = sentinel.get("target")
    mode = sentinel.get("mode", "snapshot")
    slot_payload = sentinel.get("payload")
    if target not in _CANVAS_TARGETS or mode not in ("snapshot", "delta"):
        return None
    if not isinstance(slot_payload, dict):
        return None
    return str(target), str(mode), slot_payload


__all__ = ["canvas_state_delta"]
