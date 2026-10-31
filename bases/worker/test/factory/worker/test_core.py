"""Tests for worker base core types and runtime."""

from factory.worker.core import BackendType, TaskInfo, WorkerHealth
from factory.worker.runtime.runtime import WorkerRuntime, reset_runtime


class TestCoreTypes:
    def test_backend_type_enum(self):
        assert BackendType.CELERY == "celery"
        assert BackendType.DAGSTER == "dagster"

    def test_task_info_to_dict(self):
        task = TaskInfo(name="my_task", queue="high", state="SUCCESS")
        d = task.to_dict()
        assert d["name"] == "my_task"
        assert d["queue"] == "high"
        assert d["state"] == "SUCCESS"

    def test_worker_health_to_dict(self):
        health = WorkerHealth(healthy=True, backend="celery", active_tasks=3)
        d = health.to_dict()
        assert d["healthy"] is True
        assert d["backend"] == "celery"
        assert d["active_tasks"] == 3


class TestWorkerRuntime:
    def setup_method(self):
        reset_runtime()

    def test_available_backends(self):
        assert WorkerRuntime.available_backends() == ["celery", "dagster", "fargate_sqs"]

    def test_create_celery_adapter(self):
        rt = WorkerRuntime(backend="celery", broker_url="redis://test:6379/0")
        adapter = rt.get_adapter()
        assert adapter.backend_type == "celery"

    def test_create_dagster_adapter(self):
        rt = WorkerRuntime(backend="dagster")
        adapter = rt.get_adapter()
        assert adapter.backend_type == "dagster"

    def test_invalid_backend_raises(self):
        import pytest

        with pytest.raises(ValueError):
            WorkerRuntime(backend="invalid").get_adapter()
