"""Combined Agent-side Session MCP port."""
from __future__ import annotations

from .session_completions import SessionCompletionMCP
from .session_steering import SessionSteeringMCP


class SessionAgentMCP(SessionSteeringMCP):
    def __init__(self) -> None:
        self._completions = SessionCompletionMCP()

    def pending_completions(self, request):
        return self._completions.pending(request)

    def acknowledge_completion(self, delivery):
        return self._completions.acknowledge(delivery)


__all__ = ["SessionAgentMCP"]
