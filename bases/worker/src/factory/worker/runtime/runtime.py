"""Worker runtime — adapter factory and management."""

from __future__ import annotations

from typing import Any

from ..core import BackendType, TaskInfo, WorkerHealth
from .ports import WorkerPort


class WorkerRuntime:
    """Runtime for managing worker adapters."""

    def __init__(self, backend: str = "celery", broker_url: str | None = None) -> None:
        self._backend_type = BackendType(backend)
        self._broker_url = broker_url
        self._queues: list[str] = []
        self._adapter: WorkerPort | None = None

    @property
    def backend_name(self) -> str:
        """Return the configured public backend name."""
        return self._backend_type.value

    @staticmethod
    def available_backends() -> list[str]:
        """List the only backends reachable through the Worker catalog."""
        return [backend.value for backend in BackendType]

    def switch_backend(self, backend: str, broker_url: str | None = None) -> dict[str, Any]:
        """Switch backend through the runtime owner of adapter lifecycle."""
        available = self.available_backends()
        if backend not in available:
            return {
                "switched": False,
                "backend": None,
                "available": available,
                "error": "unknown_backend",
            }
        self._backend_type = BackendType(backend)
        self._broker_url = broker_url
        self._adapter = None
        return {"switched": True, "backend": backend, "available": available, "error": None}

    def update_config(
        self,
        *,
        queues: list[str] | None = None,
        concurrency: int | None = None,
    ) -> dict[str, Any]:
        """Apply supported configuration and report unsupported settings."""
        changes: dict[str, Any] = {}
        unsupported: list[str] = []
        if queues is not None:
            self._queues = list(queues)
            changes["queues"] = list(self._queues)
        if concurrency is not None:
            unsupported.append("concurrency")
        return {
            "updated": bool(changes),
            "changes": changes,
            "unsupported": unsupported,
            "error": "unsupported_configuration" if unsupported and not changes else None,
        }

    def get_adapter(self) -> WorkerPort:
        """Get or create the worker adapter."""
        if self._adapter is None:
            self._adapter = self._create_adapter()
        return self._adapter

    def _create_adapter(self) -> WorkerPort:
        """Create adapter based on backend type."""
        if self._backend_type == BackendType.CELERY:
            from .adapters.celery import CeleryAdapter

            return CeleryAdapter(broker_url=self._broker_url)
        elif self._backend_type == BackendType.DAGSTER:
            from .adapters.dagster import DagsterAdapter

            return DagsterAdapter()
        elif self._backend_type == BackendType.FARGATE_SQS:
            from .adapters.fargate_sqs import FargateSQSAdapter

            return FargateSQSAdapter(
                queue_url=self._broker_url or "",
            )
        raise ValueError(f"Unknown backend: {self._backend_type}")

    def start(self, queues: list[str] | None = None) -> None:
        """Start the worker (blocking), using configured queues by default."""
        selected_queues = self._queues if queues is None else list(queues)
        self.get_adapter().start(selected_queues or None)

    def health_check(self) -> WorkerHealth:
        """Check worker health."""
        return self.get_adapter().health_check()

    def list_tasks(self) -> list[TaskInfo]:
        """List known tasks."""
        return self.get_adapter().list_tasks()

    def send_task(self, name: str, args: tuple = (), kwargs: dict | None = None) -> Any:
        """Dispatch a task."""
        return self.get_adapter().send_task(name, args, kwargs)


_runtime: WorkerRuntime | None = None


def get_runtime(backend: str = "celery", broker_url: str | None = None) -> WorkerRuntime:
    """Get the global worker runtime."""
    global _runtime
    if _runtime is None:
        _runtime = WorkerRuntime(backend, broker_url)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
