"""Tests for start_run idempotency."""
import pytest
import tempfile
from pathlib import Path

from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.envelope import Envelope


class TestStartRunIdempotency:
    """start_run MUST be idempotent when run_id is supplied."""

    @pytest.fixture
    def runtime(self):
        """Create a runtime with temp config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Create minimal config
            settings_file = config_dir / "settings.yaml"
            settings_file.write_text("storage:\n  backend: sqlite\n")
            
            workflows_dir = config_dir / "workflows"
            workflows_dir.mkdir()
            
            # Create a simple workflow
            workflow_file = workflows_dir / "simple.yaml"
            workflow_file.write_text(
                "id: simple\nname: Simple Workflow\nversion: 1\nsteps:\n  - id: step1\n    kind: noop\n"
            )
            
            yield WorkflowRuntime.from_config_dir(config_dir=config_dir)

    def test_start_run_with_same_run_id_returns_existing(self, runtime):
        """Calling start_run twice with same run_id should return existing run."""
        envelope = Envelope(run_id="fixed-run-id")
        
        # First call creates the run
        result1 = runtime.start_run(
            workflow_name_or_id="simple",
            input={},
            envelope=envelope,
        )
        
        # Second call with same run_id should return same run
        result2 = runtime.start_run(
            workflow_name_or_id="simple",
            input={},
            envelope=envelope,
        )
        
        assert result1["run_id"] == result2["run_id"]
        assert result1["run_id"] == "fixed-run-id"

    def test_start_run_without_run_id_generates_new(self, runtime):
        """Calling start_run without run_id should generate unique IDs."""
        envelope1 = Envelope()
        envelope2 = Envelope()
        
        result1 = runtime.start_run(
            workflow_name_or_id="simple",
            input={},
            envelope=envelope1,
        )
        
        result2 = runtime.start_run(
            workflow_name_or_id="simple",
            input={},
            envelope=envelope2,
        )
        
        assert result1["run_id"] != result2["run_id"]
