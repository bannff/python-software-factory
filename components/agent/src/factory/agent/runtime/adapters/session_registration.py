"""Session registration for chat turns that no Crew pre-created (#54)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Any

from ..runtime_contracts import RuntimeInvocation

logger = logging.getLogger(__name__)

def session_title(text: str) -> str:
    """First line of ``text``, falling back to ``New chat``."""
    lines = text.strip().splitlines()
    return lines[0][:200] if lines and lines[0] else "New chat"


def user_text(messages: list[dict[str, Any]] | None) -> str | None:
    """The latest raw user message; unlike the turn prompt it carries no
    FE-pushed context prefix."""
    for message in reversed(messages or ()):
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else None
    return None


class SessionRegistrar:
    """Idempotently ensure the thread has a Session row.

    A failure is logged and the turn proceeds: losing the listing entry must
    not cost the user the reply."""

    def __init__(self, port: Any | None = None) -> None:
        self._port = port

    async def register(
        self, request: RuntimeInvocation, messages: list[dict[str, Any]] | None = None,
    ) -> None:
        if request.tenant_id is None or request.owner_id is None:
            return
        if self._port is None:
            from .session_agent_mcp import SessionAgentMCP
            self._port = SessionAgentMCP()
        try:
            # ensure_thread titles from the prompt's first line; hand it the raw
            # user text, not the context-prefixed turn prompt.
            titled = replace(request, prompt=user_text(messages) or request.prompt)
            await asyncio.to_thread(self._port.ensure, titled)
        except Exception:  # noqa: BLE001
            logger.exception("session registration failed thread_id=%s", request.thread_id)


__all__ = ["SessionRegistrar", "session_title", "user_text"]
