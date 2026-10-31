"""Tests for the MCP-backed dataset resolver and MLX handoff."""

from __future__ import annotations

from threading import Event
from unittest.mock import Mock

import pytest

from factory.machine_learning.runtime.adapters.dataset_resolver import McpDatasetResolver
from factory.machine_learning.runtime.adapters.mlx_finetuning import MlxFineTuningAdapter
from factory.machine_learning.runtime.models import (
    DatasetTrainingInput,
    FineTuningMethod,
    ResolvedTrainingDataset,
    TrainingConfig,
)


def _training_input() -> DatasetTrainingInput:
    return DatasetTrainingInput(
        dataset_uri="file:///datasets/bundle.jsonl",
        manifest_uri="file:///datasets/manifest.json",
        dataset_digest="a" * 64,
        view_name="sft",
        view_schema_version="1.0",
    )


def _manifest() -> dict[str, object]:
    return {
        "dataset_uri": "file:///datasets/bundle.jsonl",
        "manifest_uri": "file:///datasets/manifest.json",
        "training_uri": "file:///datasets/sft.jsonl",
        "dataset_digest": "a" * 64,
        "training_views": ["sft"],
        "view_schema_versions": {"sft": "1.0"},
    }


def _envelope(data: dict[str, object] | None, *, ok: bool = True) -> dict[str, object]:
    return {"schema_version": "v1", "ok": ok, "data": data, "error": None if ok else "failed", "idempotency_key": None}


def test_mcp_resolver_validates_and_returns_training_location() -> None:
    invoker = Mock(return_value=_envelope(_manifest()))

    resolved = McpDatasetResolver(invoker).resolve(_training_input())

    assert resolved.training_uri == "file:///datasets/sft.jsonl"
    invoker.assert_called_once_with(
        "dataset_resolve_artifact", dataset_uri="file:///datasets/bundle.jsonl",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_digest", "b" * 64, "dataset manifest dataset_digest mismatch"),
        ("manifest_uri", "file:///datasets/other.json", "dataset manifest manifest_uri mismatch"),
        ("training_uri", None, "dataset manifest has no training_uri"),
    ],
)
def test_mcp_resolver_rejects_invalid_manifest(
    field: str, value: object, message: str,
) -> None:
    manifest = _manifest()
    manifest[field] = value

    with pytest.raises(ValueError, match=message):
        McpDatasetResolver(Mock(return_value=_envelope(manifest))).resolve(_training_input())


def test_mlx_resolves_before_runner_and_passes_verified_location(monkeypatch: pytest.MonkeyPatch) -> None:
    resolved = ResolvedTrainingDataset(
        training_uri="file:///datasets/sft.jsonl",
        dataset_uri=_training_input().dataset_uri,
        manifest_uri=_training_input().manifest_uri,
        dataset_digest=_training_input().dataset_digest,
        view_name="sft",
        view_schema_version="1.0",
    )
    resolver = Mock(return_value=resolved)
    runner_called = Event()
    runner = Mock(side_effect=lambda job, value, persist, complete: runner_called.set())
    monkeypatch.setattr(
        "factory.machine_learning.runtime.adapters.mlx_runner.run_mlx_training", runner,
    )
    adapter = MlxFineTuningAdapter(dataset_resolver=Mock(resolve=resolver))
    job = adapter.create_job(
        FineTuningMethod.mlx_lora,
        "base-model",
        _training_input(),
        TrainingConfig(max_iters=1),
    )

    started = adapter.start_job(job.id)

    assert started.status.value == "running"
    assert runner_called.wait(1)
    resolver.assert_called_once_with(_training_input())
    assert runner.call_args.args[1] == resolved