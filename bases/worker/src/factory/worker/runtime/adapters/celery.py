"""Celery worker adapter.

Composes workflow brick's CeleryExecutor for task dispatch.
Owns the worker process lifecycle (start/stop).
"""

from __future__ import annotations

import logging
from typing import Any

from ...core import TaskInfo, WorkerHealth

logger = logging.getLogger(__name__)


class CeleryAdapter:
    """Worker adapter using Celery.

    Delegates task dispatch to workflow's CeleryExecutor.
    Owns the blocking worker process start.
    """

    def __init__(self, broker_url: str | None = None) -> None:
        import os
        self._broker_url = broker_url or os.environ.get(
            "FACTORY_CELERY_BROKER_URL", "redis://localhost:6379/1"
        )
        self._executor = None
        self._app = None

    @property
    def backend_type(self) -> str:
        return "celery"

    def _get_executor(self):
        """Lazy-init workflow's CeleryExecutor."""
        if self._executor is None:
            from factory.workflow.runtime.execution.adapters import (
                create_executor,
            )
            self._executor = create_executor({
                "backend": "celery",
                "celery": {"broker_url": self._broker_url},
            })
            self._app = self._executor._app
            self._register_mcp_bridge()
        return self._executor

    def _register_mcp_bridge(self) -> None:
        """Wire MCP gateway tasks into the Celery app."""
        try:
            from ..bridge import register_mcp_tasks
            register_mcp_tasks(self._app)
        except Exception as e:
            logger.warning("MCP bridge unavailable: %s", e)

    def start(self, queues: list[str] | None = None) -> None:
        """Start celery worker (blocking)."""
        executor = self._get_executor()
        app = executor._app
        argv = ["worker", "--loglevel=INFO"]
        if queues:
            argv.extend(["-Q", ",".join(queues)])
        logger.info(
            "Starting Celery worker: broker=%s queues=%s",
            self._broker_url, queues,
        )
        app.worker_main(argv)

    def health_check(self) -> WorkerHealth:
        """Check celery worker health via workflow executor."""
        executor = self._get_executor()
        info = executor.health_check()
        healthy = info.get("ok", False)
        return WorkerHealth(
            healthy=healthy,
            backend="celery",
            queues=info.get("workers", []),
            error=info.get("error"),
        )

    def list_tasks(self) -> list[TaskInfo]:
        """List registered celery tasks."""
        executor = self._get_executor()
        app = executor._app
        return [
            TaskInfo(name=name, queue="default")
            for name in sorted(app.tasks.keys())
            if not name.startswith("celery.")
        ]

    def send_task(
        self, name: str, args: tuple = (), kwargs: dict | None = None,
    ) -> Any:
        """Dispatch a task via workflow executor."""
        import uuid
        executor = self._get_executor()
        result = executor.submit(
            task_id=str(uuid.uuid4()),
            task_type=name,
            payload={"args": list(args), "kwargs": kwargs or {}},
        )
        return {"task_id": result.task_id, "status": result.status.value}
