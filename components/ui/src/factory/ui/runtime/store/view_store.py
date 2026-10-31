"""View store implementations for persisting UI views."""

from datetime import datetime, timezone
from typing import Any

from ..models import UIView, ViewUpdate


class InMemoryViewStore:
    """In-memory view store implementation.

    Suitable for development and testing. For production,
    use RedisViewStore or implement a persistent store.
    """

    def __init__(self) -> None:
        self._views: dict[str, UIView] = {}
        self._history: list[ViewUpdate] = []

    def get(self, view_id: str) -> UIView | None:
        """Get a view by ID."""
        return self._views.get(view_id)

    def save(self, view: UIView) -> None:
        """Save a view."""
        is_new = view.id not in self._views
        view.updated_at = datetime.now(timezone.utc)
        if not is_new:
            view.version += 1
        self._views[view.id] = view

    def delete(self, view_id: str) -> bool:
        """Delete a view."""
        if view_id in self._views:
            del self._views[view_id]
            return True
        return False

    def list_views(self) -> list[str]:
        """List all view IDs."""
        return list(self._views.keys())

    def get_all(self) -> list[UIView]:
        """Get all views."""
        return list(self._views.values())

    def record_update(self, update: ViewUpdate) -> None:
        """Record an update in history."""
        self._history.append(update)
        # Keep last 1000 updates
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

    def get_history(self, view_id: str | None = None, limit: int = 100) -> list[ViewUpdate]:
        """Get update history, optionally filtered by view."""
        history = self._history
        if view_id:
            history = [u for u in history if u.view_id == view_id]
        return history[-limit:]

    def clear(self) -> None:
        """Clear all views and history."""
        self._views.clear()
        self._history.clear()

    def to_dict(self) -> dict[str, Any]:
        """Export store state."""
        return {
            "views": {vid: v.to_dict() for vid, v in self._views.items()},
            "history_count": len(self._history),
        }
