"""Base protocol and types for task execution adapters.

This module defines the contract that all task executors must implement,
enabling polymorphic backend selection at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class TaskStatus(str, Enum):
    """Status of a submitted task."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    status: TaskStatus
    result: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retries: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class TaskExecutor(Protocol):
    """Protocol for task execution backends.
    
    Implementations must be stateless and thread-safe.
    All methods should be idempotent where possible.
    """

    @property
    def backend_name(self) -> str:
        """Return the backend identifier (e.g., 'local', 'celery', 'dagster')."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Check backend connectivity and readiness."""
        ...

    def submit(
        self,
        *,
        task_id: str,
        task_type: str,
        payload: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Submit a task for execution.
        
        Args:
            task_id: Unique identifier for this task instance
            task_type: Type/name of the task to execute
            payload: Input data for the task
            options: Backend-specific options (queue, priority, timeout, etc.)
            
        Returns:
            TaskResult with initial status (typically PENDING)
        """
        ...

    def get_status(self, *, task_id: str) -> TaskResult:
        """Get current status of a submitted task.
        
        Args:
            task_id: The task identifier from submit()
            
        Returns:
            TaskResult with current status and result if completed
        """
        ...

    def cancel(self, *, task_id: str, reason: str | None = None) -> TaskResult:
        """Attempt to cancel a running or pending task.
        
        Args:
            task_id: The task identifier
            reason: Optional cancellation reason
            
        Returns:
            TaskResult with updated status
        """
        ...

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[TaskResult]:
        """List tasks matching the given filters.
        
        Args:
            status: Filter by task status
            task_type: Filter by task type
            limit: Maximum number of results
            
        Returns:
            List of TaskResult objects
        """
        ...
