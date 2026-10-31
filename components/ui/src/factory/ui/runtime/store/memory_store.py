from typing import Any, Dict, Optional

from ..models import SessionState


class MemoryStore:
    """
    A simple in-memory store for session states.
    In a real production environment, this would be backed by Redis or a DB.
    """

    def __init__(self):
        self._store: Dict[str, SessionState] = {}

    def get_session(self, session_id: str) -> SessionState:
        """
        Retrieves a session by ID. Creates a new one if it doesn't exist.
        """
        if session_id not in self._store:
            self._store[session_id] = SessionState(session_id=session_id)
        return self._store[session_id]

    def update_session(
        self,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
        current_path: Optional[str] = None,
    ) -> SessionState:
        """
        Updates a session's data or path.
        """
        session = self.get_session(session_id)
        if data:
            session.data.update(data)
        if current_path:
            session.current_path = current_path
        return session

    def clear_session(self, session_id: str):
        if session_id in self._store:
            del self._store[session_id]
