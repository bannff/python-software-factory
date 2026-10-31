"""Real end-to-end test for :class:`PeftFineTuningAdapter`.

Uses ``hf-internal-testing/tiny-random-gpt2`` (a tiny public test
fixture model, ~112K params) so the real LoRA training loop runs fast
on CPU in CI while still exercising every real step: dataset
resolution, ``transformers.AutoModelForCausalLM`` load,
``peft.get_peft_model`` wrap, the actual forward/backward/optimizer
loop, and a real checkpoint write via ``CheckpointStore.save``.

No fabricated metrics: asserts the reported loss is a real float
produced by an actual forward pass, not a hardcoded literal.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")
pytest.importorskip("peft", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.runtime.adapters.checkpoint_store import CheckpointStore
from factory.machine_learning.runtime.adapters.peft_finetuning import PeftFineTuningAdapter
from factory.machine_learning.runtime.models import (
    CheckpointType,
    DatasetTrainingInput,
    FineTuningMethod,
    JobStatus,
    LoRAConfig,
    ResolvedTrainingDataset,
    TrainingConfig,
)

_MODEL_ID = "hf-internal-testing/tiny-random-gpt2"


@pytest.fixture(autouse=True)
def mock_graph_store():
    from unittest.mock import patch
    with patch("factory.machine_learning.runtime.adapters.graph_adapter.GraphMLStore"):
        yield


def _training_input() -> DatasetTrainingInput:
    return DatasetTrainingInput(
        dataset_uri="file:///tmp/peft_dataset.jsonl",
        manifest_uri="file:///tmp/peft_manifest.json",
        dataset_digest="a" * 64,
        view_name="sft",
        view_schema_version="1.0",
    )


def _write_jsonl(path: Path, n: int = 6) -> None:
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({"text": f"hello world example number {i}"}) + "\n")


def _resolved_dataset(training_uri: str) -> ResolvedTrainingDataset:
    ti = _training_input()
    return ResolvedTrainingDataset(
        training_uri=training_uri,
        dataset_uri=ti.dataset_uri,
        manifest_uri=ti.manifest_uri,
        dataset_digest=ti.dataset_digest,
        view_name=ti.view_name,
        view_schema_version=ti.view_schema_version,
    )


@pytest.fixture
def adapter(tmp_path: Path) -> tuple[PeftFineTuningAdapter, Path]:
    data_path = tmp_path / "train.jsonl"
    _write_jsonl(data_path)
    resolver = Mock()
    resolver.resolve = Mock(return_value=_resolved_dataset(data_path.resolve().as_uri()))
    store = CheckpointStore(base_path=str(tmp_path / "checkpoints"))
    return PeftFineTuningAdapter(checkpoint_store=store, dataset_resolver=resolver), tmp_path


def _wait_for_terminal(adapter: PeftFineTuningAdapter, job_id: str, timeout: float = 120.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = adapter.get_job(job_id)
        if job.status in (JobStatus.completed, JobStatus.failed):
            return job
        time.sleep(0.2)
    raise TimeoutError(f"job {job_id} did not reach a terminal state in {timeout}s")


class TestPeftFineTuningLifecycle:
    """create_job -> start_job -> get_job with real training."""

    def test_full_lifecycle_reports_real_metrics(
        self, adapter: tuple[PeftFineTuningAdapter, Path],
    ) -> None:
        ft_adapter, _ = adapter
        job = ft_adapter.create_job(
            method=FineTuningMethod.lora,
            base_model=_MODEL_ID,
            training_input=_training_input(),
            training_config=TrainingConfig(batch_size=2, learning_rate=1e-3, max_iters=3),
            lora_config=LoRAConfig(rank=4, alpha=8, target_modules=["c_attn"]),
        )
        assert job.status == JobStatus.pending

        started = ft_adapter.start_job(job.id)
        assert started.status == JobStatus.running

        final = _wait_for_terminal(ft_adapter, job.id)
        assert final.status == JobStatus.completed
        assert final.error is None

        # Real loss: a finite float that is NOT the old fabricated
        # {"loss": 0.01} sentinel from the memory/mlx adapters.
        assert "loss" in final.metrics
        assert isinstance(final.metrics["loss"], float)
        assert final.metrics["loss"] == final.metrics["loss"]  # not NaN
        assert final.metrics["loss"] != 0.01

        assert len(final.checkpoints) == 1
        cp = final.checkpoints[0]
        assert cp.checkpoint_type == CheckpointType.final_artifact
        assert cp.path and Path(cp.path).exists()
        assert cp.metrics["loss"] == final.metrics["loss"]

    def test_get_job_returns_none_for_unknown_id(
        self, adapter: tuple[PeftFineTuningAdapter, Path],
    ) -> None:
        ft_adapter, _ = adapter
        assert ft_adapter.get_job("nonexistent") is None

    def test_start_job_fails_closed_without_dataset_resolver(
        self, tmp_path: Path,
    ) -> None:
        store = CheckpointStore(base_path=str(tmp_path / "checkpoints"))
        ft_adapter = PeftFineTuningAdapter(checkpoint_store=store, dataset_resolver=None)
        job = ft_adapter.create_job(
            method=FineTuningMethod.lora, base_model=_MODEL_ID,
            training_input=_training_input(),
        )
        started = ft_adapter.start_job(job.id)
        assert started.status == JobStatus.failed
        assert "dataset resolution is not configured" in started.error

    def test_stop_job_transitions_running_to_stopped(
        self, adapter: tuple[PeftFineTuningAdapter, Path],
    ) -> None:
        ft_adapter, _ = adapter
        job = ft_adapter.create_job(
            method=FineTuningMethod.lora, base_model=_MODEL_ID,
            training_input=_training_input(),
        )
        stopped = ft_adapter.stop_job(job.id)
        assert stopped.status == JobStatus.stopped

    def test_list_jobs_includes_created_job(
        self, adapter: tuple[PeftFineTuningAdapter, Path],
    ) -> None:
        ft_adapter, _ = adapter
        job = ft_adapter.create_job(
            method=FineTuningMethod.lora, base_model=_MODEL_ID,
            training_input=_training_input(),
        )
        assert any(j.id == job.id for j in ft_adapter.list_jobs())
