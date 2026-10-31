"""Hypothesis property tests for MlxFineTuningAdapter."""

import uuid
import time
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings, strategies as st

from factory.machine_learning.runtime.models import (
    DatasetTrainingInput, FineTuningMethod, JobStatus, TrainingConfig, LoRAConfig
)
from factory.machine_learning.runtime.adapters.mlx_finetuning import MlxFineTuningAdapter

# We patch GraphMLStore at its source to ensure integration side-effects don't bleed into property tests
@pytest.fixture(autouse=True)
def mock_graph_store():
    with patch("factory.machine_learning.runtime.adapters.graph_adapter.GraphMLStore") as mock:
        yield mock

@pytest.fixture(autouse=True)
def mock_emit_event():
    with patch("factory.machine_learning.runtime.adapters.mlx_finetuning.emit_ml_event") as mock:
        yield mock


def training_input() -> DatasetTrainingInput:
    return DatasetTrainingInput(
        dataset_uri="file:///tmp/dataset.jsonl",
        manifest_uri="file:///tmp/manifest.json",
        dataset_digest="0" * 64,
        view_name="sft",
        view_schema_version="1.0",
    )

@given(
    base_model=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    max_iters=st.integers(min_value=1, max_value=100)
)
@settings(max_examples=20, deadline=1000)
def test_mlx_finetuning_lifecycle(base_model, max_iters):
    adapter = MlxFineTuningAdapter(checkpoint_store=None)
    
    # 1. Create Job
    job = adapter.create_job(
        method=FineTuningMethod.mlx_lora,
        base_model=base_model,
        training_input=training_input(),
        training_config=TrainingConfig(max_iters=max_iters),
        lora_config=LoRAConfig()
    )
    assert job.status == JobStatus.pending
    assert job.base_model == base_model
    
    # 2. Get Job
    retrieved = adapter.get_job(job.id)
    assert retrieved == job
    
    # 3. List Jobs
    assert job in adapter.list_jobs()
    
    # 4. Start Job without a dataset resolver: fail closed before MLX starts.
    with patch("factory.machine_learning.runtime.adapters.mlx_finetuning.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Success output", "")
        mock_popen.return_value = mock_proc
        
        started_job = adapter.start_job(job.id)
        assert started_job.status in (JobStatus.running, JobStatus.failed)
        
        # Wait a tiny bit for the worker to persist its failure.
        time.sleep(0.05)
        
        final_job = adapter.get_job(job.id)
        assert final_job.status == JobStatus.failed
        assert "dataset resolution is not configured" in final_job.error
        mock_popen.assert_not_called()

@given(
    base_model=st.text(min_size=1, max_size=10, alphabet="abcdefg")
)
@settings(max_examples=10, deadline=1000)
def test_mlx_finetuning_failure(base_model):
    adapter = MlxFineTuningAdapter(checkpoint_store=None)
    
    job = adapter.create_job(
        method=FineTuningMethod.mlx_lora,
        base_model=base_model,
        training_input=training_input(),
        training_config=TrainingConfig(max_iters=1),
        lora_config=LoRAConfig()
    )
    
    with patch("factory.machine_learning.runtime.adapters.mlx_finetuning.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = ("Traceback Error!", "")
        mock_popen.return_value = mock_proc
        
        adapter.start_job(job.id)
        
        time.sleep(0.05)
        
        final_job = adapter.get_job(job.id)
        assert final_job.status == JobStatus.failed
        assert "dataset resolution is not configured" in final_job.error
        mock_popen.assert_not_called()
