"""Dagster worker adapter (daemon mode).

Composes workflow brick's DagsterExecutor for task dispatch.
Owns the daemon process lifecycle (start/stop).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

from ...core import TaskInfo, WorkerHealth

logger = logging.getLogger(__name__)


class DagsterAdapter:
    """Worker adapter using Dagster daemon.

    Delegates task dispatch to workflow's DagsterExecutor.
    Owns the blocking daemon start.
    """

    def __init__(self, dagster_home: str | None = None) -> None:
        self._dagster_home = dagster_home
        self._executor = None

    @property
    def backend_type(self) -> str:
        return "dagster"

    def _get_executor(self):
        """Lazy-init workflow's DagsterExecutor."""
        if self._executor is None:
            from factory.workflow.runtime.execution.adapters import (
                create_executor,
            )
            config: dict[str, Any] = {"backend": "dagster"}
            if self._dagster_home:
                config["dagster"] = {
                    "instance_config": {"base_dir": self._dagster_home},
                }
            self._executor = create_executor(config)
        return self._executor

    def start(self, queues: list[str] | None = None) -> None:
        """Start dagster daemon (blocking)."""
        import os

        env = os.environ.copy()
        if self._dagster_home:
            env["DAGSTER_HOME"] = self._dagster_home
        logger.info(
            "Starting Dagster daemon: DAGSTER_HOME=%s", self._dagster_home,
        )
        subprocess.run(
            [sys.executable, "-m", "dagster", "daemon", "run"],
            env=env,
            check=True,
        )

    def health_check(self) -> WorkerHealth:
        """Check dagster daemon health via workflow executor."""
        executor = self._get_executor()
        info = executor.health_check()
        healthy = info.get("ok", False)
        return WorkerHealth(
            healthy=healthy,
            backend="dagster",
            error=info.get("error"),
        )

    def list_tasks(self) -> list[TaskInfo]:
        """Dagster uses jobs/ops, not tasks. Returns empty list."""
        return []

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
