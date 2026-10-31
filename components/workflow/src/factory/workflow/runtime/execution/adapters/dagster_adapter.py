"""Dagster pipeline executor adapter.

Pipeline orchestration via Dagster. Requires dagster package.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .base import TaskResult, TaskStatus

if TYPE_CHECKING:
    from dagster import DagsterInstance


_STATUS_MAP = {
    "NOT_STARTED": TaskStatus.PENDING, "QUEUED": TaskStatus.PENDING,
    "STARTING": TaskStatus.RUNNING, "STARTED": TaskStatus.RUNNING,
    "SUCCESS": TaskStatus.SUCCEEDED, "FAILURE": TaskStatus.FAILED,
    "CANCELED": TaskStatus.CANCELLED, "CANCELING": TaskStatus.CANCELLED,
}


class DagsterExecutor:
    """Dagster-based pipeline executor."""

    def __init__(self, instance: "DagsterInstance") -> None:
        self._instance = instance
        self._job_registry: dict[str, Any] = {}

    @classmethod
    def from_instance(cls, instance_config: dict[str, Any] | None = None) -> "DagsterExecutor":
        """Create executor from Dagster instance configuration."""
        try:
            from dagster import DagsterInstance
        except ImportError as e:
            raise ImportError("Dagster required. Install: pip install dagster") from e

        instance = DagsterInstance.from_config(instance_config) if instance_config else DagsterInstance.get()
        return cls(instance)

    @classmethod
    def from_grpc(cls, host: str = "localhost", port: int = 4266) -> "DagsterExecutor":
        """Create executor connecting to a remote Dagster gRPC server."""
        try:
            from dagster import DagsterInstance
        except ImportError as e:
            raise ImportError("Dagster required. Install: pip install dagster") from e

        executor = cls(DagsterInstance.get())
        executor._grpc_host = host
        executor._grpc_port = port
        return executor

    def register_job(self, task_type: str, job: Any) -> None:
        """Register a Dagster job for a task type."""
        self._job_registry[task_type] = job

    @property
    def backend_name(self) -> str:
        return "dagster"

    def health_check(self) -> dict[str, Any]:
        try:
            runs = self._instance.get_runs(limit=1)
            return {
                "ok": True, "backend": "dagster",
                "registered_jobs": list(self._job_registry.keys()),
            }
        except Exception as e:
            return {"ok": False, "backend": "dagster", "error": str(e)}

    def submit(
        self, *, task_id: str, task_type: str, payload: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> TaskResult:
        opts = options or {}
        job = self._job_registry.get(task_type)
        
        if job is None:
            return TaskResult(
                task_id=task_id, status=TaskStatus.FAILED,
                error=f"No job registered for task type: {task_type}",
            )

        try:
            run_config = opts.get("run_config", {})
            if payload:
                run_config.setdefault("ops", {})["config"] = payload

            run = self._instance.create_run_for_job(
                job_def=job, run_id=task_id, run_config=run_config,
                tags=opts.get("tags", {}),
            )
            self._instance.launch_run(run.run_id, None)

            return TaskResult(
                task_id=run.run_id, status=TaskStatus.PENDING,
                started_at=datetime.now(timezone.utc),
                metadata={"task_type": task_type, "job_name": job.name},
            )
        except Exception as e:
            return TaskResult(task_id=task_id, status=TaskStatus.FAILED, error=str(e))

    def get_status(self, *, task_id: str) -> TaskResult:
        run = self._instance.get_run_by_id(task_id)
        if run is None:
            return TaskResult(task_id=task_id, status=TaskStatus.FAILED, error="Run not found")

        status = _STATUS_MAP.get(run.status.value, TaskStatus.PENDING)
        return TaskResult(
            task_id=task_id, status=status,
            result={"dagster_status": run.status.value} if status == TaskStatus.SUCCEEDED else None,
            error=run.failure_reason if run.failure_reason else None,
            started_at=run.start_time, completed_at=run.end_time,
            metadata={"dagster_status": run.status.value, "job_name": run.job_name},
        )

    def cancel(self, *, task_id: str, reason: str | None = None) -> TaskResult:
        try:
            self._instance.report_run_canceling(task_id)
            return TaskResult(
                task_id=task_id, status=TaskStatus.CANCELLED,
                completed_at=datetime.now(timezone.utc), error=reason or "Cancelled",
            )
        except Exception as e:
            return TaskResult(task_id=task_id, status=TaskStatus.FAILED, error=str(e))

    def list_tasks(
        self, *, status: TaskStatus | None = None, task_type: str | None = None,
        limit: int = 100,
    ) -> list[TaskResult]:
        try:
            from dagster import DagsterRunStatus, RunsFilter
        except ImportError:
            return []

        filters = RunsFilter(job_name=task_type) if task_type else RunsFilter()
        runs = self._instance.get_runs(filters=filters, limit=limit)
        
        return [
            TaskResult(
                task_id=run.run_id,
                status=_STATUS_MAP.get(run.status.value, TaskStatus.PENDING),
                started_at=run.start_time, completed_at=run.end_time,
                metadata={"job_name": run.job_name},
            )
            for run in runs
        ]
