"""Carrier #2 (canvas paint) handler for the chat-stream → AG-UI mapper.

Extracted from ``ag_ui_mapper_chat`` to keep that file under the 200-LOC
brick tenet (bd-D pre-condition iv). Implements ``_on_state_delta`` and
exports the ``canvas_seeded`` mapper-state default.

The producer is the MCP tool ``ui_paint_canvas`` (carrier #2 in
``.agents/steering/a2ui-protocol.md``). The flow is:

* ``AfterToolCallEvent`` fires on ``ui_paint_canvas`` returning a tagged
  ``_a2ui_canvas`` result.
* ``factory.agent.plugins.state_delta_plugin`` synthesizes a
  ``StateDeltaEvent`` onto the per-turn chat queue (alongside the
  normal ``ToolResultEvent`` from ``ag_ui_bridge``).
* This handler runs once per ``StateDeltaEvent`` and emits either
  ``STATE_SNAPSHOT`` (first paint of the run — seeds ``state.canvas={}``)
  or ``STATE_DELTA`` with an RFC 6902 ``replace`` op on
  ``/canvas/<target>``.

Hard pre-conditions (meta-architect verdict
``2dabeff1-eee0-47cc-9d98-1165ebc88e96`` Q10):

(ii) JSON Patch discipline — emit ``STATE_SNAPSHOT`` first to seed the
     ``canvas`` object, then ``replace`` per slot. ``add`` on a missing
     parent fails silently in fast-json-patch (``console.warn`` on the FE
     and no re-render).
(iv) ``canvas_seeded`` resets per-turn naturally — the mapper state is
     per-stream and the chat SSE handler creates a fresh
     ``AGUIStreamState`` on every run.
"""
from __future__ import annotations

import time
from typing import Any

from .ag_ui_mapper import AGUIEventType


def _ts() -> float:
    return time.time()


def on_state_delta(
    event: Any, state: Any, close_reasoning: Any,
) -> list[dict[str, Any]]:
    """Translate a ``StateDeltaEvent`` to AG-UI ``STATE_*`` events.

    Args:
        event: The pydantic ``StateDeltaEvent`` instance.
        state: Per-turn ``AGUIStreamState`` — mutates ``canvas_seeded``.
        close_reasoning: Reference to the mapper's
            ``_close_reasoning_if_open`` helper. Passed in to avoid a
            cross-import cycle with the mapper module.
    """
    out: list[dict[str, Any]] = close_reasoning(state)
    target = event.target
    payload = event.payload
    mode = event.mode

    # First paint of the run OR explicit snapshot request: emit
    # STATE_SNAPSHOT carrying the full ``canvas`` object so the FE
    # reducer sees ``state.canvas`` exist before any subsequent
    # ``replace`` patches arrive.
    if mode == "snapshot" or not state.canvas_seeded:
        state.canvas_seeded = True
        out.append({
            "type": AGUIEventType.STATE_SNAPSHOT,
            "snapshot": {"canvas": {target: payload}},
            "timestamp": _ts(),
        })
        return out

    # Subsequent paints: RFC 6902 ``replace`` on the canvas slot.
    out.append({
        "type": AGUIEventType.STATE_DELTA,
        "delta": [{"op": "replace",
                   "path": f"/canvas/{target}",
                   "value": payload}],
        "timestamp": _ts(),
    })
    return out


__all__ = ["on_state_delta"]
