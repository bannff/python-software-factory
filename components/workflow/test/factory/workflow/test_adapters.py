"""Tests for task execution adapters."""

import pytest
from factory.workflow.runtime.execution.adapters import (
    TaskExecutor,
    TaskResult,
    TaskStatus,
    LocalExecutor,
    create_executor,
)


class TestLocalExecutor:
    """Tests for LocalExecutor."""

    def test_backend_name(self):
        executor = LocalExecutor()
        assert executor.backend_name == "local"

    def test_health_check(self):
        executor = LocalExecutor()
        result = executor.health_check()
        assert result["ok"] is True
        assert result["backend"] == "local"

    def test_submit_unknown_task_fails(self):
        executor = LocalExecutor()
        result = executor.submit(
            task_id="test-1",
            task_type="unknown",
            payload={"key": "value"},
        )
        assert result.task_id == "test-1"
        assert result.status == TaskStatus.FAILED
        assert "unknown task type" in result.error.lower()

    def test_submit_with_handler(self):
        executor = LocalExecutor()
        executor.register_handler("double", lambda p: {"result": p.get("x", 0) * 2})
        
        result = executor.submit(
            task_id="test-2",
            task_type="double",
            payload={"x": 21},
        )
        assert result.status == TaskStatus.SUCCEEDED
        assert result.result == {"result": 42}

    def test_submit_handler_error(self):
        executor = LocalExecutor()
        executor.register_handler("fail", lambda p: 1 / 0)
        
        result = executor.submit(
            task_id="test-3",
            task_type="fail",
            payload={},
        )
        assert result.status == TaskStatus.FAILED
        assert "ZeroDivisionError" in result.error

    def test_get_status(self):
        executor = LocalExecutor()
        executor.register_handler("noop", lambda payload: {"ok": True})
        executor.submit(task_id="test-4", task_type="noop", payload={})
        
        result = executor.get_status(task_id="test-4")
        assert result.task_id == "test-4"
        assert result.status == TaskStatus.SUCCEEDED

    def test_get_status_not_found(self):
        executor = LocalExecutor()
        result = executor.get_status(task_id="nonexistent")
        assert result.status == TaskStatus.FAILED
        assert "not found" in result.error.lower()

    def test_cancel_pending(self):
        executor = LocalExecutor()
        executor.register_handler("noop", lambda payload: {"ok": True})
        # Submit completes immediately for local, so we can't really test pending
        # But we can test the cancel path
        executor.submit(task_id="test-5", task_type="noop", payload={})
        result = executor.cancel(task_id="test-5", reason="Testing")
        # Already succeeded, so cancel returns current state
        assert result.status == TaskStatus.SUCCEEDED

    def test_list_tasks(self):
        executor = LocalExecutor()
        executor.clear()
        
        executor.submit(task_id="t1", task_type="a", payload={})
        executor.submit(task_id="t2", task_type="b", payload={})
        executor.submit(task_id="t3", task_type="a", payload={})
        
        all_tasks = executor.list_tasks()
        assert len(all_tasks) == 3
        
        type_a = executor.list_tasks(task_type="a")
        assert len(type_a) == 2

    def test_idempotent_submit(self):
        executor = LocalExecutor()
        r1 = executor.submit(task_id="same", task_type="x", payload={})
        r2 = executor.submit(task_id="same", task_type="y", payload={})
        assert r1.task_id == r2.task_id


class TestCreateExecutor:
    """Tests for executor factory."""

    def test_default_local(self):
        executor = create_executor()
        assert executor.backend_name == "local"

    def test_explicit_local(self):
        executor = create_executor({"backend": "local"})
        assert executor.backend_name == "local"

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown executor backend"):
            create_executor({"backend": "unknown"})

    def test_celery_missing_broker(self):
        with pytest.raises(ValueError, match="broker_url"):
            create_executor({"backend": "celery", "celery": {}})


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_defaults(self):
        result = TaskResult(task_id="x", status=TaskStatus.PENDING)
        assert result.result is None
        assert result.error is None
        assert result.retries == 0
        assert result.metadata == {}


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCEEDED.value == "succeeded"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
