"""Local in-process task executor.

Default executor that runs tasks synchronously in the current process.
No external dependencies required. Useful for development and testing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
import threading
import traceback

from .base import TaskExecutor, TaskResult, TaskStatus


class LocalExecutor:
    """In-process task executor for development and testing.
    
    Tasks run synchronously in the calling thread by default.
    Maintains an in-memory registry of task results.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, TaskResult] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._lock = threading.Lock()

    @property
    def backend_name(self) -> str:
        return "local"

    def health_check(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": True,
                "backend": "local",
                "tasks_in_memory": len(self._tasks),
                "registered_handlers": list(self._handlers.keys()),
            }

    def register_handler(self, task_type: str, handler: Callable[..., Any]) -> None:
        """Register a handler function for a task type.
        
        Args:
            task_type: The task type identifier
            handler: Callable that accepts payload dict and returns result
        """
        with self._lock:
            self._handlers[task_type] = handler

    def submit(
        self,
        *,
        task_id: str,
        task_type: str,
        payload: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> TaskResult:
        now = datetime.now(timezone.utc)
        
        with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id]
            
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                started_at=now,
                metadata={"task_type": task_type, "options": options or {}},
            )
            self._tasks[task_id] = result

        # Execute synchronously
        return self._execute(task_id, task_type, payload)

    def _execute(
        self, task_id: str, task_type: str, payload: dict[str, Any]
    ) -> TaskResult:
        now = datetime.now(timezone.utc)
        
        with self._lock:
            handler = self._handlers.get(task_type)
            result = self._tasks.get(task_id)
            
            if result is None:
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error="Task not found",
                )
            
            result.status = TaskStatus.RUNNING
            self._tasks[task_id] = result

        if handler is None:
            with self._lock:
                result.status = TaskStatus.FAILED
                result.completed_at = now
                result.error = f"Unknown task type: {task_type}"
                self._tasks[task_id] = result
            return result

        try:
            output = handler(payload)
            with self._lock:
                result.status = TaskStatus.SUCCEEDED
                result.completed_at = datetime.now(timezone.utc)
                result.result = output
                self._tasks[task_id] = result
        except Exception as e:
            with self._lock:
                result.status = TaskStatus.FAILED
                result.completed_at = datetime.now(timezone.utc)
                result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                self._tasks[task_id] = result

        return result

    def get_status(self, *, task_id: str) -> TaskResult:
        with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id]
        
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error="Task not found",
        )

    def cancel(self, *, task_id: str, reason: str | None = None) -> TaskResult:
        with self._lock:
            if task_id not in self._tasks:
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error="Task not found",
                )
            
            result = self._tasks[task_id]
            if result.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
                return result
            
            result.status = TaskStatus.CANCELLED
            result.completed_at = datetime.now(timezone.utc)
            result.error = reason or "Cancelled by user"
            self._tasks[task_id] = result
            return result

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[TaskResult]:
        with self._lock:
            results = list(self._tasks.values())
        
        if status is not None:
            results = [r for r in results if r.status == status]
        
        if task_type is not None:
            results = [
                r for r in results 
                if r.metadata.get("task_type") == task_type
            ]
        
        return results[:limit]

    def clear(self) -> None:
        """Clear all tasks from memory. Useful for testing."""
        with self._lock:
            self._tasks.clear()
