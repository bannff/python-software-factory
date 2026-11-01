"""Session registration for chat turns that no Crew pre-created (#54)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..runtime_contracts import RuntimeInvocation

logger = logging.getLogger(__name__)

# Mirrors bases/api ag_ui_input.prefix_context; a title must come from what the
# user typed, not from the context block the API prepends to the prompt.
_CONTEXT_PREFIX = "Canvas context (system-supplied, FE-pushed):"


def session_title(prompt: str) -> str:
    """First line of the user's own message, falling back to ``New chat``."""
    text = prompt.strip()
    if text.startswith(_CONTEXT_PREFIX):
        text = text.partition("\n\n")[2].strip()
    lines = text.splitlines()
    return lines[0][:200] if lines and lines[0] else "New chat"


class SessionRegistrar:
    """Idempotently ensure the thread has a Session row.

    A failure is logged and the turn proceeds: losing the listing entry must
    not cost the user the reply."""

    def __init__(self, port: Any | None = None) -> None:
        self._port = port

    async def register(self, request: RuntimeInvocation) -> None:
        if request.tenant_id is None or request.owner_id is None:
            return
        if self._port is None:
            from .session_agent_mcp import SessionAgentMCP
            self._port = SessionAgentMCP()
        try:
            await asyncio.to_thread(self._port.ensure, request)
        except Exception:  # noqa: BLE001
            logger.exception("session registration failed thread_id=%s", request.thread_id)


__all__ = ["SessionRegistrar", "session_title"]
