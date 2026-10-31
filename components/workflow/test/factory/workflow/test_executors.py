"""Tests for workflow task executors.

Tests LocalExecutor and executor factory.
"""

from __future__ import annotations

import pytest

from factory.workflow.runtime.execution.adapters import (
    LocalExecutor,
    TaskStatus,
    TaskResult,
    create_executor,
)


class TestLocalExecutor:
    """Tests for LocalExecutor."""

    @pytest.fixture
    def executor(self) -> LocalExecutor:
        """Create a fresh executor for each test."""
        return LocalExecutor()

    def test_backend_name(self, executor: LocalExecutor) -> None:
        """Test backend name is 'local'."""
        assert executor.backend_name == "local"

    def test_health_check(self, executor: LocalExecutor) -> None:
        """Test health check returns ok."""
        health = executor.health_check()

        assert health["ok"] is True
        assert health["backend"] == "local"
        assert health["tasks_in_memory"] == 0

    def test_submit_task_unknown_type_fails(self, executor: LocalExecutor) -> None:
        """Unknown task types fail loudly instead of becoming no-ops."""
        result = executor.submit(
            task_id="test-1",
            task_type="noop_task",
            payload={"key": "value"},
        )

        assert result.task_id == "test-1"
        assert result.status == TaskStatus.FAILED
        assert "unknown task type" in (result.error or "").lower()

    def test_submit_task_with_handler(self, executor: LocalExecutor) -> None:
        """Test submitting a task with registered handler."""

        def my_handler(payload: dict) -> dict:
            return {"processed": payload["input"] * 2}

        executor.register_handler("double", my_handler)
        result = executor.submit(
            task_id="test-2",
            task_type="double",
            payload={"input": 5},
        )

        assert result.status == TaskStatus.SUCCEEDED
        assert result.result["processed"] == 10

    def test_submit_task_handler_error(self, executor: LocalExecutor) -> None:
        """Test task failure when handler raises exception."""

        def failing_handler(payload: dict) -> dict:
            raise ValueError("Something went wrong")

        executor.register_handler("failing", failing_handler)
        result = executor.submit(
            task_id="test-3",
            task_type="failing",
            payload={},
        )

        assert result.status == TaskStatus.FAILED
        assert "ValueError" in result.error
        assert "Something went wrong" in result.error

    def test_get_status(self, executor: LocalExecutor) -> None:
        """Test getting task status."""
        executor.register_handler("noop", lambda payload: {"ok": True})
        executor.submit(task_id="test-4", task_type="noop", payload={})

        result = executor.get_status(task_id="test-4")

        assert result.task_id == "test-4"
        assert result.status == TaskStatus.SUCCEEDED

    def test_get_status_not_found(self, executor: LocalExecutor) -> None:
        """Test getting status of non-existent task."""
        result = executor.get_status(task_id="nonexistent")

        assert result.status == TaskStatus.FAILED
        assert "not found" in result.error.lower()

    def test_cancel_pending_task(self, executor: LocalExecutor) -> None:
        """Test cancelling a task."""
        # Submit and immediately try to cancel (local executor runs sync)
        executor.register_handler("noop", lambda payload: {"ok": True})
        executor.submit(task_id="test-5", task_type="noop", payload={})

        # Task already completed, cancel should return current state
        result = executor.cancel(task_id="test-5", reason="User requested")

        # Already succeeded, so cancel doesn't change status
        assert result.status == TaskStatus.SUCCEEDED

    def test_cancel_not_found(self, executor: LocalExecutor) -> None:
        """Test cancelling non-existent task."""
        result = executor.cancel(task_id="nonexistent")

        assert result.status == TaskStatus.FAILED
        assert "not found" in result.error.lower()

    def test_list_tasks_empty(self, executor: LocalExecutor) -> None:
        """Test listing tasks when empty."""
        tasks = executor.list_tasks()

        assert tasks == []

    def test_list_tasks_with_filter(self, executor: LocalExecutor) -> None:
        """Test listing tasks with status filter."""
        executor.register_handler("type_a", lambda payload: {})
        executor.register_handler("type_b", lambda payload: {})
        executor.submit(task_id="t1", task_type="type_a", payload={})
        executor.submit(task_id="t2", task_type="type_b", payload={})

        # All succeeded
        tasks = executor.list_tasks(status=TaskStatus.SUCCEEDED)
        assert len(tasks) == 2

        # Filter by type
        tasks = executor.list_tasks(task_type="type_a")
        assert len(tasks) == 1
        assert tasks[0].task_id == "t1"

    def test_list_tasks_limit(self, executor: LocalExecutor) -> None:
        """Test listing tasks with limit."""
        executor.register_handler("test", lambda payload: {})
        for i in range(5):
            executor.submit(task_id=f"t{i}", task_type="test", payload={})

        tasks = executor.list_tasks(limit=3)
        assert len(tasks) == 3

    def test_clear(self, executor: LocalExecutor) -> None:
        """Test clearing all tasks."""
        executor.register_handler("test", lambda payload: {})
        executor.submit(task_id="t1", task_type="test", payload={})
        executor.submit(task_id="t2", task_type="test", payload={})

        executor.clear()

        assert executor.list_tasks() == []
        health = executor.health_check()
        assert health["tasks_in_memory"] == 0

    def test_idempotent_submit(self, executor: LocalExecutor) -> None:
        """Test that submitting same task_id returns existing result."""
        executor.register_handler("test", lambda payload: {})
        result1 = executor.submit(task_id="same-id", task_type="test", payload={})
        result2 = executor.submit(task_id="same-id", task_type="test", payload={})

        assert result1.task_id == result2.task_id
        assert result1.status == result2.status


class TestExecutorFactory:
    """Tests for create_executor factory function."""

    def test_default_creates_local(self) -> None:
        """Test that default config creates local executor."""
        executor = create_executor()

        assert executor.backend_name == "local"

    def test_explicit_local_backend(self) -> None:
        """Test explicit local backend config."""
        executor = create_executor({"backend": "local"})

        assert executor.backend_name == "local"
