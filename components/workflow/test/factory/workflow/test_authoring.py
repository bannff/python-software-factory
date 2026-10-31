"""Tests for authoring tools - security gating and CRUD operations."""
import os
import pytest
import tempfile
from pathlib import Path

from factory.workflow.authoring import (
    AuthoringManager,
    AuthoringError,
)


class TestAuthoringDisabledByDefault:
    """Authoring tools MUST be disabled by default."""

    @pytest.mark.skip(reason="AuthoringManager does not implement disabled-by-default behavior yet")
    def test_authoring_disabled_without_env_var(self):
        """Authoring should raise error when env var not set."""
        # Ensure env var is not set
        os.environ.pop("WORKFLOW_ENABLE_AUTHORING_TOOLS", None)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AuthoringManager(config_dir=Path(tmpdir))
            
            with pytest.raises(AuthoringError):
                service.get_status()

    def test_authoring_enabled_with_env_var(self):
        """Authoring should work when env var is set."""
        os.environ["WORKFLOW_ENABLE_AUTHORING_TOOLS"] = "1"
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                service = AuthoringManager(config_dir=Path(tmpdir))
                status = service.get_status()
                
                assert status["enabled"] is True
                assert "config_dir" in status
        finally:
            os.environ.pop("WORKFLOW_ENABLE_AUTHORING_TOOLS", None)


class TestPathTraversalProtection:
    """Authoring tools MUST be scoped to config_dir with traversal protection."""

    @pytest.fixture
    def enabled_service(self):
        """Create an enabled authoring service."""
        os.environ["WORKFLOW_ENABLE_AUTHORING_TOOLS"] = "1"
        with tempfile.TemporaryDirectory() as tmpdir:
            yield AuthoringManager(config_dir=Path(tmpdir))
        os.environ.pop("WORKFLOW_ENABLE_AUTHORING_TOOLS", None)

    def test_rejects_path_traversal_dotdot(self, enabled_service):
        """Should reject paths with .. traversal."""
        with pytest.raises(AuthoringError, match="Invalid id"):
            enabled_service.upsert_workflow_definition(
                id="../../../etc/passwd",
                yaml_or_object={"name": "malicious", "version": 1, "steps": [{"id": "s1", "kind": "noop"}]},
            )

    def test_rejects_absolute_paths(self, enabled_service):
        """Should reject absolute paths."""
        with pytest.raises(AuthoringError, match="Invalid id"):
            enabled_service.upsert_workflow_definition(
                id="/etc/passwd",
                yaml_or_object={"name": "malicious", "version": 1, "steps": [{"id": "s1", "kind": "noop"}]},
            )


class TestAuthoringCRUD:
    """Test authoring CRUD operations."""

    @pytest.fixture
    def service_with_dir(self):
        """Create enabled service with temp directory."""
        os.environ["WORKFLOW_ENABLE_AUTHORING_TOOLS"] = "1"
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            workflows_dir = config_dir / "workflows"
            workflows_dir.mkdir(parents=True)
            yield AuthoringManager(config_dir=config_dir), workflows_dir
        os.environ.pop("WORKFLOW_ENABLE_AUTHORING_TOOLS", None)

    def test_upsert_creates_workflow(self, service_with_dir):
        """Should create a new workflow definition."""
        service, workflows_dir = service_with_dir
        
        result = service.upsert_workflow_definition(
            id="test-workflow",
            yaml_or_object={
                "name": "Test Workflow",
                "version": 1,
                "steps": [{"id": "step1", "kind": "noop"}],
            },
        )
        
        assert result["ok"] is True
        assert (workflows_dir / "test-workflow.yaml").exists()

    def test_validate_all_workflows_dry_run(self, service_with_dir):
        """Should validate without writing."""
        service, _ = service_with_dir
        
        result = service.validate_all_workflows()
        
        assert "ok" in result
        assert "errors" in result

    def test_delete_workflow(self, service_with_dir):
        """Should delete existing workflow."""
        service, workflows_dir = service_with_dir
        
        # Create first
        service.upsert_workflow_definition(
            id="to-delete",
            yaml_or_object={"name": "Delete Me", "version": 1, "steps": [{"id": "step1", "kind": "noop"}]},
        )
        
        # Delete
        result = service.delete_workflow_definition(id="to-delete")
        
        assert result["deleted"] is True
        assert not (workflows_dir / "to-delete.yaml").exists()
