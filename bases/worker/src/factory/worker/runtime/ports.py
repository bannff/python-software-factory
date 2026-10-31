"""Worker ports — Protocol interfaces for worker adapters."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..core import TaskInfo, WorkerHealth


@runtime_checkable
class WorkerPort(Protocol):
    """Port: background task worker."""

    @property
    def backend_type(self) -> str:
        """Unique identifier for this backend type."""
        ...

    def start(self, queues: list[str] | None = None) -> None:
        """Start the worker process (blocking)."""
        ...

    def health_check(self) -> WorkerHealth:
        """Check worker health."""
        ...

    def list_tasks(self) -> list[TaskInfo]:
        """List known/active tasks."""
        ...

    def send_task(self, name: str, args: tuple = (), kwargs: dict | None = None) -> Any:
        """Dispatch a task for execution."""
        ...
