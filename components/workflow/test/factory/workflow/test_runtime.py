"""Tests for WorkflowRuntime runtime factory.

Tests runtime initialization, configuration, and runtime flags.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWorkflowRuntimeFactory:
    """Tests for WorkflowRuntime.from_config_dir factory method."""

    def test_missing_settings_raises(self, tmp_path: Path) -> None:
        """Test that missing settings.yaml raises WorkflowError."""
        from factory.workflow.runtime.operations import WorkflowError
        from factory.workflow.runtime.runtime import WorkflowRuntime

        with pytest.raises(WorkflowError, match="Missing settings.yaml"):
            WorkflowRuntime.from_config_dir(tmp_path)

    def test_invalid_settings_raises(self, tmp_path: Path) -> None:
        """Test that invalid settings.yaml raises WorkflowError."""
        from factory.workflow.runtime.operations import WorkflowError
        from factory.workflow.runtime.runtime import WorkflowRuntime

        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text("not a mapping")

        with pytest.raises(WorkflowError, match="must parse to a mapping"):
            WorkflowRuntime.from_config_dir(tmp_path)

    def test_creates_runtime_with_valid_config(self, tmp_path: Path) -> None:
        """Test runtime creation with valid minimal config."""
        from factory.workflow.runtime.runtime import WorkflowRuntime

        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            """
storage:
  sqlite:
    filename: workflow.db
executor:
  backend: local
"""
        )

        runtime = WorkflowRuntime.from_config_dir(tmp_path)

        assert runtime is not None
        assert runtime.config_dir == tmp_path.resolve()
        assert runtime.executor.backend_name == "local"

    def test_loads_workflow_definitions(self, tmp_path: Path) -> None:
        """Test that workflow definitions are loaded from workflows/ dir."""
        from factory.workflow.runtime.runtime import WorkflowRuntime

        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            """
storage:
  sqlite:
    filename: workflow.db
executor:
  backend: local
"""
        )

        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()
        (workflows_dir / "test-workflow.yaml").write_text(
            """
id: test-workflow
name: Test Workflow
version: "1.0"
steps:
  - id: start
    kind: noop
"""
        )

        runtime = WorkflowRuntime.from_config_dir(tmp_path)
        registry = runtime.get_workflow_registry()

        assert len(registry) == 1
        assert registry[0]["id"] == "test-workflow"
        assert registry[0]["name"] == "Test Workflow"


class TestRuntimeFlags:
    """Tests for runtime flag management."""

    def test_default_flags(self, tmp_path: Path) -> None:
        """Test default runtime flags."""
        from factory.workflow.runtime.runtime import WorkflowRuntime

        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            """
storage:
  sqlite:
    filename: workflow.db
executor:
  backend: local
"""
        )

        runtime = WorkflowRuntime.from_config_dir(tmp_path)

        assert runtime.flags.authoring_enabled is False
        assert runtime.flags.running_mode == "stdio"

    def test_set_runtime_flags(self, tmp_path: Path) -> None:
        """Test setting runtime flags."""
        from factory.workflow.runtime.runtime import WorkflowRuntime

        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            """
storage:
  sqlite:
    filename: workflow.db
executor:
  backend: local
"""
        )

        runtime = WorkflowRuntime.from_config_dir(tmp_path)
        runtime.set_runtime_flags(authoring_enabled=True, running_mode="http")

        assert runtime.flags.authoring_enabled is True
        assert runtime.flags.running_mode == "http"


class TestExecutorCreation:
    """Tests for executor backend creation."""

    def test_local_executor_default(self, tmp_path: Path) -> None:
        """Test that local executor is created by default."""
        from factory.workflow.runtime.runtime import WorkflowRuntime

        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            """
storage:
  sqlite:
    filename: workflow.db
executor:
  backend: local
"""
        )

        runtime = WorkflowRuntime.from_config_dir(tmp_path)

        assert runtime.executor.backend_name == "local"
        health = runtime.executor.health_check()
        assert health["ok"] is True
