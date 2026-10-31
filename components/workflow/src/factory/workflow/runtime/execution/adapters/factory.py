"""Factory for creating task executors from configuration.

Provides a unified way to instantiate the appropriate executor backend
based on configuration, enabling runtime backend selection.
"""

from __future__ import annotations

from typing import Any

from .base import TaskExecutor, TaskResult, TaskStatus
from .local import LocalExecutor


def create_executor(config: dict[str, Any] | None = None) -> TaskExecutor:
    """Create a task executor from configuration.
    
    Args:
        config: Executor configuration dict with structure:
            {
                "backend": "local" | "celery" | "dagster",
                "celery": {"broker_url": "...", "result_backend": "..."},
                "dagster": {"host": "...", "port": ...},
            }
            
    Returns:
        Configured TaskExecutor instance
        
    Raises:
        ValueError: If backend is unknown
        ImportError: If required backend package is not installed
    """
    if config is None:
        return LocalExecutor()
    
    backend = config.get("backend", "local")
    
    if backend == "local":
        return LocalExecutor()
    
    if backend == "celery":
        from .celery_adapter import CeleryExecutor
        
        celery_config = config.get("celery", {})
        broker_url = celery_config.get("broker_url")
        
        if not broker_url:
            raise ValueError("Celery backend requires 'celery.broker_url' in config")
        
        return CeleryExecutor.from_broker_url(
            broker_url=broker_url,
            result_backend=celery_config.get("result_backend"),
            app_name=celery_config.get("app_name", "factory-workflow"),
        )
    
    if backend == "dagster":
        from .dagster_adapter import DagsterExecutor
        
        dagster_config = config.get("dagster", {})
        
        if "host" in dagster_config:
            return DagsterExecutor.from_grpc(
                host=dagster_config.get("host", "localhost"),
                port=dagster_config.get("port", 4266),
            )
        
        return DagsterExecutor.from_instance(
            instance_config=dagster_config.get("instance_config")
        )
    
    raise ValueError(f"Unknown executor backend: {backend}")


__all__ = [
    "create_executor",
    "TaskExecutor",
    "TaskResult",
    "TaskStatus",
    "LocalExecutor",
]
