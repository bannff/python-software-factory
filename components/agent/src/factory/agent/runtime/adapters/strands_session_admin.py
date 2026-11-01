"""Durable-transcript operations over the SQL-backed Strands session repo."""
from __future__ import annotations

from typing import Any

from .strands_session_repository import SqlSessionRepository


class StrandsSessionAdmin:
    """Delete, fork and read a thread's persisted transcript (all personas)."""

    def __init__(self, repo: SqlSessionRepository | None = None) -> None:
        self._repo = repo or SqlSessionRepository()

    def delete_thread(self, thread_id: str) -> None:
        suffix = f"-{thread_id}"
        for session_id in self._repo.session_ids():
            if session_id.endswith(suffix):
                self._repo.delete_session(session_id)

    def fork(self, agent_id: str, source_thread_id: str, target_thread_id: str) -> bool:
        """False when the source has no durable history."""
        return self._repo.fork_session(
            f"{agent_id}-{source_thread_id}", f"{agent_id}-{target_thread_id}",
        )

    def history(self, agent_id: str, thread_id: str) -> list[dict[str, Any]]:
        """The durable transcript in AG-UI message shape."""
        from .strands_history import session_messages_to_agui
        return session_messages_to_agui(self._repo, f"{agent_id}-{thread_id}")


__all__ = ["StrandsSessionAdmin"]
