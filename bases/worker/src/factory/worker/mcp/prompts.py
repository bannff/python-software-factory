"""Worker MCP prompts."""
from __future__ import annotations

from typing import Callable

from typing import Any


def register(mcp: Any, get_runtime: Callable) -> None:
    """Register native Worker prompts."""

    @mcp.prompt()
    def configure_worker() -> str:
        """Guide for configuring a Worker backend."""
        backends = get_runtime().available_backends()
        return (
            "Configure a background task worker.\n\n"
            f"Available backends: {', '.join(backends)}\n\n"
            "Steps:\n"
            "1. Set FACTORY_WORKER_BACKEND to celery, dagster, or fargate_sqs\n"
            "2. Set FACTORY_CELERY_BROKER_URL, or an SQS queue URL for fargate_sqs\n"
            "3. Optionally set FACTORY_WORKER_QUEUES\n"
            "4. Do not set concurrency: it is not supported by this runtime\n"
            "5. Run the worker entry point\n"
        )

    @mcp.prompt()
    def debug_worker() -> str:
        """Guide for debugging Worker issues."""
        return (
            "Debug a worker issue.\n\n"
            "1. Check worker_health_check for redacted connectivity status\n"
            "2. Check worker_list_tasks for registered or pending tasks\n"
            "3. Verify the configured broker or fargate_sqs queue URL\n"
            "4. Check the bridge allowlist and principal when using worker.execute_tool\n"
            "5. Check worker logs for provider diagnostics\n"
        )


__all__ = ["register"]
