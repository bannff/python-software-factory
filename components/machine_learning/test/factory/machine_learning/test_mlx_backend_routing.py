"""P0 routing and CLI flag tests for the MLX fine-tuning backend (dim.7)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.machine_learning.mcp import operational
from factory.machine_learning.runtime.adapters import mlx_runner
from factory.machine_learning.runtime.models import (
    DatasetTrainingInput,
    FineTuningJob,
    FineTuningMethod,
    LoRAConfig,
    ResolvedTrainingDataset,
    TrainingConfig,
)


def _resolved() -> ResolvedTrainingDataset:
    return ResolvedTrainingDataset(
        training_uri="file:///tmp/train.jsonl",
        dataset_uri="file:///tmp/dataset.jsonl",
        manifest_uri="file:///tmp/manifest.json",
        dataset_digest="0" * 64,
        view_name="sft",
        view_schema_version="1.0",
    )


def _job(method: FineTuningMethod, lora: LoRAConfig | None = None) -> FineTuningJob:
    return FineTuningJob(
        id="job-1",
        method=method,
        base_model="mlx-community/test",
        training_input=DatasetTrainingInput(
            dataset_uri="file:///tmp/dataset.jsonl",
            manifest_uri="file:///tmp/manifest.json",
            dataset_digest="0" * 64,
            view_name="sft",
            view_schema_version="1.0",
        ),
        training_config=TrainingConfig(max_iters=10, batch_size=2, learning_rate=1e-4),
        lora_config=lora or LoRAConfig(rank=16, alpha=32, dropout=0.1),
    )


def _register_with_runtime(backend_choices: list[str]) -> Any:
    """Register the operational tools with a runtime that records backend picks."""
    mcp = ToolCatalog("ml-test")

    def get_runtime() -> Any:
        rt = MagicMock(name="runtime")
        finetuner = MagicMock(name="finetuner")
        finetuner.create_job.return_value = _job(FineTuningMethod.mlx_lora)
        rt.get_finetuner.side_effect = (
            lambda backend, **_: backend_choices.append(backend) or finetuner
        )
        return rt

    operational.register(mcp, get_runtime)
    return asyncio.run(mcp.get_tool("ml_create_finetuning_job"))


# -- Fix 1: backend routing --------------------------------------------------


class TestMLXBackendRouting:
    """ml_create_finetuning_job must select the right backend."""

    def test_mlx_lora_routes_to_mlx_backend(self) -> None:
        backend_choices: list[str] = []
        tool = _register_with_runtime(backend_choices)
        tool.fn(
            method="mlx_lora", base_model="mlx-community/test",
            dataset_uri="file:///tmp/dataset.jsonl",
            manifest_uri="file:///tmp/manifest.json",
            dataset_digest="0" * 64, view_name="sft", view_schema_version="1.0",
        )
        assert backend_choices == ["mlx"]

    @pytest.mark.parametrize(
        "method", ["lora", "adalora", "ia3", "prefix_tuning", "full"],
    )
    def test_non_mlx_methods_route_to_memory_backend(self, method: str) -> None:
        backend_choices: list[str] = []
        tool = _register_with_runtime(backend_choices)
        tool.fn(
            method=method, base_model="mlx-community/test",
            dataset_uri="file:///tmp/dataset.jsonl",
            manifest_uri="file:///tmp/manifest.json",
            dataset_digest="0" * 64, view_name="sft", view_schema_version="1.0",
        )
        assert backend_choices == ["memory"]


# -- Fix 2: CLI flag forwarding ---------------------------------------------


class TestMlxCliFlagForwarding:
    """LoRA + TrainingConfig fields must reach the mlx_lm subprocess."""

    def test_lora_flags_appear_in_subprocess_command(self) -> None:
        job = _job(FineTuningMethod.mlx_lora, LoRAConfig(
            rank=32, alpha=64, dropout=0.2,
            target_modules=["q_proj", "k_proj", "v_proj"],
        ))

        with patch.object(mlx_runner.subprocess, "Popen") as mock_popen:
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = ("Iter 10: Train loss 1.234, ...", "")
            mock_popen.return_value = proc
            mlx_runner.run_mlx_training(
                job, _resolved(), persist_fn=lambda j: None, on_complete=lambda jid: None,
            )
            cmd = mock_popen.call_args.args[0]

        def has(flag: str, value: str) -> bool:
            return flag in cmd and cmd[cmd.index(flag) + 1] == value

        assert has("--lora-rank", "32"), cmd
        assert has("--lora-alpha", "64"), cmd
        assert has("--lora-dropout", "0.2"), cmd
        assert has("--target-modules", "q_proj,k_proj,v_proj"), cmd
        assert has("--batch-size", "2"), cmd
        assert has("--learning-rate", "0.0001"), cmd
        assert has("--max-seq-length", "512"), cmd


# -- Fix 3: metric parsing ---------------------------------------------------


class TestMlxMetricParsing:
    """``run_mlx_training`` must capture the real loss, not a constant."""

    def test_parses_final_train_loss_from_mlx_output(self) -> None:
        job = _job(FineTuningMethod.mlx_lora)
        stdout = (
            "Iter 1: Train loss 2.512, Learning Rate 1.000e-04, ...\n"
            "Iter 5: Train loss 1.842, Learning Rate 1.000e-04, ...\n"
            "Iter 10: Train loss 0.987, Learning Rate 1.000e-04, ...\n"
        )
        with patch.object(mlx_runner.subprocess, "Popen") as mock_popen:
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = (stdout, "")
            mock_popen.return_value = proc
            mlx_runner.run_mlx_training(
                job, _resolved(), persist_fn=lambda j: None, on_complete=lambda jid: None,
            )
        assert job.status.value == "completed"
        assert job.metrics == {"loss": 0.987}
        assert job.checkpoints[-1].metrics["loss"] == 0.987

    def test_parses_alternative_step_bracket_format(self) -> None:
        """Defensive: the spec also mentions ``[step N/M] loss=X``."""
        job = _job(FineTuningMethod.mlx_lora)
        stdout = "[step 1/10] loss=3.210\n[step 10/10] loss=0.555\n"
        with patch.object(mlx_runner.subprocess, "Popen") as mock_popen:
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate.return_value = (stdout, "")
            mock_popen.return_value = proc
            mlx_runner.run_mlx_training(
                job, _resolved(), persist_fn=lambda j: None, on_complete=lambda jid: None,
            )
        assert job.metrics == {"loss": 0.555}
