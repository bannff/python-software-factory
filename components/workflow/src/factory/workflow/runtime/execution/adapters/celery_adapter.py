"""Celery task executor adapter.

Distributed task execution via Celery. Requires celery package and a broker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .base import TaskResult, TaskStatus

if TYPE_CHECKING:
    from celery import Celery
    from celery.result import AsyncResult


_STATE_MAP = {
    "PENDING": TaskStatus.PENDING,
    "STARTED": TaskStatus.RUNNING,
    "RETRY": TaskStatus.RETRYING,
    "SUCCESS": TaskStatus.SUCCEEDED,
    "FAILURE": TaskStatus.FAILED,
    "REVOKED": TaskStatus.CANCELLED,
}


class CeleryExecutor:
    """Celery-based distributed task executor."""

    def __init__(self, app: "Celery") -> None:
        self._app = app
        self._task_name = "factory.workflow.execute_task"
        self._ensure_task_registered()

    @classmethod
    def from_broker_url(
        cls, broker_url: str, *, result_backend: str | None = None,
        app_name: str = "factory-workflow",
    ) -> "CeleryExecutor":
        """Create executor from broker URL."""
        try:
            from celery import Celery
        except ImportError as e:
            raise ImportError("Celery required. Install: pip install celery[redis]") from e

        app = Celery(app_name, broker=broker_url, backend=result_backend or broker_url)
        app.conf.update(
            task_serializer="json", accept_content=["json"], result_serializer="json",
            timezone="UTC", enable_utc=True, task_track_started=True, result_extended=True,
        )
        return cls(app)

    def _ensure_task_registered(self) -> None:
        if self._task_name not in self._app.tasks:
            @self._app.task(name=self._task_name, bind=True)
            def execute_task(self_task: Any, payload: dict[str, Any]) -> dict[str, Any]:
                return {"status": "executed", "payload": payload}

    @property
    def backend_name(self) -> str:
        return "celery"

    def health_check(self) -> dict[str, Any]:
        try:
            ping_result = self._app.control.inspect().ping()
            if ping_result:
                workers = list(ping_result.keys())
                return {"ok": True, "backend": "celery", "workers": workers}
            return {"ok": False, "backend": "celery", "error": "No workers responding"}
        except Exception as e:
            return {"ok": False, "backend": "celery", "error": str(e)}

    def submit(
        self, *, task_id: str, task_type: str, payload: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> TaskResult:
        opts = options or {}
        celery_opts: dict[str, Any] = {
            "task_id": task_id, "args": [{"task_type": task_type, **payload}],
        }
        for key in ("queue", "priority", "countdown", "expires", "retry"):
            if key in opts:
                celery_opts[key] = opts[key]

        task = self._app.tasks[self._task_name]
        async_result: AsyncResult = task.apply_async(**celery_opts)

        return TaskResult(
            task_id=async_result.id, status=TaskStatus.PENDING,
            started_at=datetime.now(timezone.utc),
            metadata={"task_type": task_type, "celery_task": self._task_name},
        )

    def get_status(self, *, task_id: str) -> TaskResult:
        async_result: AsyncResult = self._app.AsyncResult(task_id)
        status = _STATE_MAP.get(async_result.state, TaskStatus.PENDING)
        
        result_data, error, completed_at = None, None, None
        if async_result.ready():
            completed_at = datetime.now(timezone.utc)
            if async_result.successful():
                result_data = async_result.result
            else:
                error = str(async_result.result) if async_result.result else "Unknown error"

        return TaskResult(
            task_id=task_id, status=status, result=result_data, error=error,
            completed_at=completed_at, retries=async_result.retries or 0,
            metadata={"celery_state": async_result.state},
        )

    def cancel(self, *, task_id: str, reason: str | None = None) -> TaskResult:
        self._app.control.revoke(task_id, terminate=True)
        return TaskResult(
            task_id=task_id, status=TaskStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc), error=reason or "Revoked",
        )

    def list_tasks(
        self, *, status: TaskStatus | None = None, task_type: str | None = None,
        limit: int = 100,
    ) -> list[TaskResult]:
        # Celery doesn't natively support listing all tasks
        return []
