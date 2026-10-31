"""Worker base entry point — starts a background task worker.

Usage:
    uv run <project-script-name>   # e.g. companion-worker
    python -m factory.worker.main  # direct invocation
"""

from __future__ import annotations

import logging


def main() -> None:
    """Start the worker process (blocking)."""
    logging.basicConfig(level=logging.INFO)

    from factory.mcp_utils.interface import get_infra
    backend = get_infra("worker.backend", "celery")
    broker_url = get_infra("worker.broker.url", "redis://localhost:6379/1")
    queues_raw = get_infra("worker.queues", "")
    queues = [q.strip() for q in queues_raw.split(",") if q.strip()] or None

    from .runtime.runtime import get_runtime

    runtime = get_runtime(backend=backend, broker_url=broker_url)
    runtime.start(queues=queues)


if __name__ == "__main__":
    main()
