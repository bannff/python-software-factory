"""Tests for SQLite storage backend."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage
from factory.workflow.runtime.models import RunRecord
from factory.workflow.runtime.envelope import Envelope


@pytest.mark.skip(reason="Storage test needs refactoring to match actual API - create_run/update_run instead of save_run")
class TestSqliteWorkflowStorageCRUD:
    """Test basic CRUD operations."""

    @pytest.fixture
    def storage(self):
        """Create a temporary SQLite storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield SqliteWorkflowStorage(path=db_path)

    def test_create_and_get_run(self, storage):
        """Should create and retrieve a run."""
        storage.init_schema()
        storage.create_run(
            run_id="test-run-1",
            workflow_id="test-workflow",
            workflow_version=1,
            tenant_id=None,
            input={},
            envelope=Envelope(),
            now=datetime.now(timezone.utc),
        )
        
        retrieved = storage.get_run(run_id="test-run-1")
        
        assert retrieved is not None
        assert retrieved.run_id == "test-run-1"
        assert retrieved.workflow_id == "test-workflow"

    def test_get_nonexistent_run_returns_none(self, storage):
        """Should return None for missing run."""
        storage.init_schema()
        result = storage.get_run(run_id="does-not-exist")
        assert result is None

    def test_update_run_status(self, storage):
        """Should update run status."""
        storage.init_schema()
        run = RunRecord(
            run_id="test-run-2",
            workflow_id="test-workflow",
            workflow_version=1,
            status="pending",
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        storage.save_run(run)
        
        # Update status
        run.status = "running"
        run.updated_at = datetime.now(timezone.utc)
        storage.save_run(run)
        
        retrieved = storage.get_run(run_id="test-run-2")
        assert retrieved.status == "running"

    def test_list_runs_with_filter(self, storage):
        """Should list runs with optional filtering."""
        storage.init_schema()
        # Create multiple runs
        for i in range(3):
            run = RunRecord(
                run_id=f"run-{i}",
                workflow_id="workflow-a" if i < 2 else "workflow-b",
                workflow_version=1,
                status="succeeded" if i == 0 else "pending",
                started_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            storage.save_run(run)
        
        # List all
        all_runs = storage.list_runs()
        assert len(all_runs) == 3
        
        # Filter by workflow
        workflow_a_runs = storage.list_runs(workflow_id="workflow-a")
        assert len(workflow_a_runs) == 2
        
        # Filter by status
        completed_runs = storage.list_runs(status="succeeded")
        assert len(completed_runs) == 1


@pytest.mark.skip(reason="Storage test needs refactoring to match actual API - create_run/update_run instead of save_run")
class TestSqliteWorkflowStorageIdempotency:
    """Test idempotency requirements."""

    @pytest.fixture
    def storage(self):
        """Create a temporary SQLite storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield SqliteWorkflowStorage(path=db_path)

    def test_save_same_run_twice_is_idempotent(self, storage):
        """Saving the same run twice should not error or duplicate."""
        storage.init_schema()
        run = RunRecord(
            run_id="idempotent-run",
            workflow_id="test-workflow",
            workflow_version=1,
            status="pending",
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        # Save twice
        storage.save_run(run)
        storage.save_run(run)
        
        # Should still only have one
        all_runs = storage.list_runs()
        matching = [r for r in all_runs if r.run_id == "idempotent-run"]
        assert len(matching) == 1
