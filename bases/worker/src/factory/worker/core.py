"""Core types and models for worker base."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BackendType(str, Enum):
    """Supported worker backends."""

    CELERY = "celery"
    DAGSTER = "dagster"
    FARGATE_SQS = "fargate_sqs"


@dataclass
class TaskInfo:
    """Information about a registered task."""

    name: str
    queue: str = "default"
    state: str = "PENDING"
    result: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "queue": self.queue,
            "state": self.state,
            "result": self.result,
        }


@dataclass
class WorkerHealth:
    """Health status for worker."""

    healthy: bool
    backend: str
    active_tasks: int = 0
    queues: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "backend": self.backend,
            "active_tasks": self.active_tasks,
            "queues": self.queues,
            "error": self.error,
        }
