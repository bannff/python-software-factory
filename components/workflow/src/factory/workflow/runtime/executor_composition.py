"""Compose configured legacy task executors."""
from __future__ import annotations

from typing import Any

from .execution.adapters import TaskExecutor, create_executor
from .models import Settings


def create_configured_executor(settings: Settings) -> TaskExecutor:
    executor = settings.executor
    config: dict[str, Any] = {"backend": executor.backend}
    if executor.backend == "celery":
        config["celery"] = {
            "broker_url": executor.celery.broker_url,
            "result_backend": executor.celery.result_backend,
            "app_name": executor.celery.app_name,
        }
    elif executor.backend == "dagster":
        config["dagster"] = {
            "host": executor.dagster.host, "port": executor.dagster.port,
            "instance_config": executor.dagster.instance_config,
        }
    return create_executor(config)
