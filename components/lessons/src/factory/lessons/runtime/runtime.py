"""Lessons runtime composition."""
from __future__ import annotations

import os

from factory.storage.interface import get_sql_store

from .adapters.sql import SQLLessonStore
from .lifecycle import LessonLifecycle


class LessonsRuntime:
    def __init__(self, lifecycle: LessonLifecycle | None = None) -> None:
        self._lifecycle = lifecycle

    @property
    def lifecycle(self) -> LessonLifecycle:
        if self._lifecycle is None:
            path = os.getenv("COMPANION_X_LESSONS_DB_PATH", "./.storage/lessons.db")
            self._lifecycle = LessonLifecycle(
                SQLLessonStore(get_sql_store("sqlite", db_path=path)),
            )
        return self._lifecycle

    @staticmethod
    def health_check() -> dict[str, object]:
        return {"healthy": True, "backend": "sqlite"}

    async def reconcile_projections(self, limit: int = 100) -> tuple[str, ...]:
        from .projection import project_accepted
        return await project_accepted(self.lifecycle.store, limit)

    async def recall(
        self, tenant_id: str, owner_id: str, persona_id: str,
        query: str, limit: int = 8,
    ):
        from .recall import recall
        return await recall(
            self.lifecycle.store, tenant_id, owner_id, persona_id, query, limit,
        )


_runtime: LessonsRuntime | None = None


def get_runtime() -> LessonsRuntime:
    global _runtime
    if _runtime is None:
        _runtime = LessonsRuntime()
    return _runtime


__all__ = ["LessonsRuntime", "get_runtime"]
