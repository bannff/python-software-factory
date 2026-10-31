"""Worker MCP resources."""
from __future__ import annotations

from typing import Callable

from typing import Any

from .projections import health_payload


def register(mcp: Any, get_runtime: Callable) -> None:
    """Register native Worker resources."""

    @mcp.resource("worker://health")
    def worker_health() -> dict:
        """Live, redacted Worker health status."""
        runtime = get_runtime()
        try:
            return health_payload(runtime.health_check(), runtime.available_backends())
        except Exception:
            return {
                "healthy": False,
                "backend": runtime.backend_name,
                "active_tasks": 0,
                "queues": [],
                "error": "worker_health_unavailable",
            }

    @mcp.resource("worker://backends")
    def worker_backends() -> dict:
        """Available Worker backends."""
        return {"backends": get_runtime().available_backends()}

    @mcp.resource("worker://docs")
    def worker_docs() -> str:
        """Worker base documentation."""
        return (
            "# Worker Base\n\n"
            "Background task execution with pluggable backends.\n\n"
            "## Backends\n"
            "- **celery**: Distributed task queue via Redis/RabbitMQ broker\n"
            "- **dagster**: Data pipeline orchestration daemon\n"
            "- **fargate_sqs**: ECS Fargate worker consuming an SQS queue\n\n"
            "## Configuration\n"
            "- `FACTORY_WORKER_BACKEND`: celery | dagster | fargate_sqs\n"
            "- `FACTORY_CELERY_BROKER_URL`: Broker URL for celery\n"
            "- `FACTORY_WORKER_QUEUES`: Comma-separated queue names\n"
            "- `concurrency`: currently unsupported by the Worker runtime\n"
        )


__all__ = ["register"]
