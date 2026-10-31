"""Wiring for strands durable sessions: repository-backed ``SessionManager``.

One factory-level helper keeps ``strands_chat.py`` under its LOC ceiling:
the manager construction (repo + ``RepositorySessionManager``) is the only
strands-session import surface the chat facade needs.
"""
from __future__ import annotations

from strands.session.repository_session_manager import RepositorySessionManager

from .strands_session_repository import SqlSessionRepository


class StrandsSessionManager(RepositorySessionManager):
    """``RepositorySessionManager`` over the default SQL session repository."""


def build_session_manager(session_id: str) -> RepositorySessionManager:
    """Build a durable ``RepositorySessionManager`` for one thread-key session."""
    return StrandsSessionManager(session_id, SqlSessionRepository())


__all__ = ["StrandsSessionManager", "build_session_manager"]
