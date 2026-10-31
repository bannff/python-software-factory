"""Task execution adapters for workflow orchestration.

This module provides pluggable backends for executing workflow tasks:
- LocalExecutor: In-process execution (default, no external deps)
- CeleryExecutor: Distributed task queue via Celery
- DagsterExecutor: Pipeline orchestration via Dagster

All adapters implement the TaskExecutor protocol defined in base.py.

Usage:
    from factory.workflow.runtime.execution.adapters import create_executor
    
    # Default local executor
    executor = create_executor()
    
    # Celery executor
    executor = create_executor({
        "backend": "celery",
        "celery": {"broker_url": "redis://localhost:6379/0"}
    })
    
    # Dagster executor
    executor = create_executor({
        "backend": "dagster",
        "dagster": {"host": "localhost", "port": 4266}
    })
"""

from .base import TaskExecutor, TaskResult, TaskStatus
from .local import LocalExecutor
from .factory import create_executor

__all__ = [
    "TaskExecutor",
    "TaskResult",
    "TaskStatus",
    "LocalExecutor",
    "create_executor",
]
