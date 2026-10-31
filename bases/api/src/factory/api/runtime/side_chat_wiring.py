"""Gateway wiring for the side-chat scratch conversation (feature-map row 19).

Composes the real dependencies — the ambient chat model, the live
tool-category lookup, and the MCP aggregator's dispatch — into a
:class:`SideChatService`, then mounts it as the `side/{open,turn,close}`
HTTP routes via :func:`side_routes.register_side_routes`.

This is the ~2-line seam every earlier slice was built and injected against:
every layer beneath it (policy, gate, conversation store, executor, service,
HTTP router, the LLM planner) is already unit-tested in isolation — this
module's only job is composition, so it stays a thin, readable wire-up
rather than a place new logic accumulates.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from factory.llm_gateway.interface import (
    CONFIGURED_CHAT_MODEL_ENV,
    configured_chat_model_id,
)

logger = logging.getLogger(__name__)

#: Explicit override for the side panel's planning model. Unset in practice,
#: which is what lets the side panel follow the deployment's chat model.
_OVERRIDE_ENV = "SIDE_CHAT_MODEL_ID"

#: Last planner build outcome, read by ``/api/health``. The wiring never fails
#: route registration, so this is how a degraded side panel becomes visible.
_planner_status: dict[str, str] = {"status": "unknown"}


def resolve_side_chat_model_id() -> str:
    """Return the model id the side-chat planner plans with, or fail naming
    what to set.

    Derived from the SAME configured chat model the rest of Companion-X
    resolves (``COMPANION_X_CHAT_MODEL`` — the model chat turns and the model
    picker default to), so the side panel can no longer diverge onto a
    provider the deployment was not configured for (issue #41).
    """
    model_id = (
        os.getenv(_OVERRIDE_ENV, "").strip() or configured_chat_model_id()
    )
    if not model_id:
        raise ValueError(
            f"no chat model configured for the side panel: "
            f"set {CONFIGURED_CHAT_MODEL_ENV}"
        )
    return model_id


def side_chat_status() -> dict[str, str]:
    """Planner status snapshot for ``/api/health`` (never raises)."""
    return dict(_planner_status)


def _record_planner_status(status: str, **details: str) -> None:
    """Replace the snapshot — a stale ``reason``/``model_id`` from an earlier
    registration must never mix into the current one."""
    _planner_status.clear()
    _planner_status.update({"status": status, **details})


def register_side_chat(app: Any) -> None:
    from factory.mcp_utils.runtime.side_chat_service import SideChatService
    from factory.mcp_utils.runtime.side_llm_complete import build_mcp_utils_complete
    from factory.mcp_utils.runtime.side_planner import build_llm_side_planner
    from .side_routes import register_side_routes

    def category_lookup() -> dict[str, str]:
        # Resolved fresh per turn: bricks load lazily, so an early-boot
        # lookup could see fewer tools than are actually available later.
        from factory.mcp_server.runtime.category_lookup import build_category_lookup
        return build_category_lookup()

    def dispatch(tool_name: str, args: dict[str, Any]) -> Any:
        import asyncio

        from .bridge import _get_aggregator
        agg = _get_aggregator()
        if agg is None:
            raise RuntimeError("MCP aggregator unavailable")
        result = agg.invoke_tool(tool_name, **args)
        if asyncio.iscoroutine(result):
            # SideChatService.turn is synchronous (built pure/testable), and
            # this dispatch runs inside the `side/turn` request handler
            # OUTSIDE any running event loop (FastAPI runs sync endpoints in
            # a worker thread), so a fresh loop here is safe — same shape as
            # bridge.py's own `await`, just from a sync call site.
            result = asyncio.run(result)
        return result

    try:
        model_id = resolve_side_chat_model_id()
        complete = build_mcp_utils_complete(model_id)
        planner = build_llm_side_planner(complete, category_lookup)
    except Exception as exc:
        # Deliberate stance (unchanged): a misconfigured model must never
        # fail route registration — the panel still opens/records turns, it
        # just can't run tools. But the degradation must be visible, so this
        # is ONE line naming the configuration to fix (no traceback: every
        # boot used to bury a single missing variable behind exc_info noise),
        # and `side_chat_status()` reports the same reason to /api/health.
        reason = " ".join(str(exc).split()) or type(exc).__name__
        logger.warning(
            "[side_chat] planner unavailable: %s; side turns will run no tools", reason,
        )
        _record_planner_status("unavailable", reason=reason)
        planner = lambda query: []  # noqa: E731
    else:
        _record_planner_status("ready", model_id=model_id)

    service = SideChatService(planner=planner, category_lookup=category_lookup, dispatch=dispatch)
    register_side_routes(app, lambda: service)


__all__ = ["register_side_chat", "resolve_side_chat_model_id", "side_chat_status"]
