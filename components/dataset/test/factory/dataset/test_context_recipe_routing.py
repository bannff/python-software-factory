"""Typed context artifact routing and materialization regressions."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factory.dataset.mcp.operational import register
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import (
    LocalDatasetMaterializer,
    LocalDatasetStore,
    _request_digest,
)
from factory.dataset.runtime.recipe import path_from_uri, resolve_recipe
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def _snapshot(root: Path, label: str, payload: dict) -> DatasetSnapshotRef:
    content = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = root / f"{label}-{digest}.json"
    path.write_bytes(content)
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _request(
    root: Path, recipe_uri: str, inputs: list[DatasetInputRef], config: dict,
) -> DatasetGenerationRequest:
    tool = _snapshot(root, "tools", {"allowed_tools": []})
    return DatasetGenerationRequest(
        recipe_uri=recipe_uri,
        recipe_digest=hashlib.sha256(recipe_uri.encode()).hexdigest(),
        input_artifacts=inputs,
        context_snapshot=_snapshot(root, "context", config),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri=tool.uri, digest=tool.digest, allowed_tools=[],
        ),
    )


def _input(path: Path, role: str | None = None) -> DatasetInputRef:
    return DatasetInputRef(
        uri=path.as_uri(), digest=hashlib.sha256(path.read_bytes()).hexdigest(),
        artifact_role=role,
    )


def test_optional_artifact_role_is_domain_neutral_and_hash_stable(tmp_path: Path):
    source = tmp_path / "source.jsonl"
    source.write_text("{}\n")
    implicit = _request(tmp_path, "recipe://local/pass-through@1", [_input(source)], {})
    explicit = _request(tmp_path, "recipe://local/pass-through@1", [
        DatasetInputRef(uri=source.as_uri(), digest=_input(source).digest, artifact_role=None),
    ], {})
    assert _request_digest(implicit) == _request_digest(explicit)
    assert "artifact_role" not in implicit.input_artifacts[0].model_dump(exclude_none=True)
    assert DatasetInputRef(
        uri=source.as_uri(), digest=_input(source).digest,
        artifact_role="primary_observation",
    ).artifact_role == "primary_observation"


@pytest.mark.parametrize(
    "uris,digests,roles,match",
    [
        (["file:///a"], [], None, "uris and input_artifact_digests"),
        (["file:///a"], ["a" * 64], [], "input_artifact_roles"),
    ],
)
def test_mcp_flat_input_lengths_fail_closed(tmp_path, uris, digests, roles, match):
    mcp = ToolCatalog("dataset-test")
    register(mcp, tmp_path)
    tool = asyncio.run(mcp.get_tool("dataset_submit_generation"))
    result = tool.fn({
        "recipe_uri": "recipe://local/pass-through@1", "recipe_digest": "a" * 64,
        "context_snapshot_uri": "file:///context", "context_snapshot_digest": "b" * 64,
        "tool_schema_snapshot_uri": "file:///tools", "tool_schema_snapshot_digest": "c" * 64,
        "input_artifact_uris": uris, "input_artifact_digests": digests,
        "input_artifact_roles": roles,
    })
    assert result.ok is False and result.data is None
    assert result.error == "tool_execution_failed"


def test_mcp_flat_input_roles_propagate(tmp_path, monkeypatch):
    captured = []

    def submit(request, _storage_root):
        captured.append(request)
        return type("Receipt", (), {"model_dump": lambda self, mode: {"job_id": "job-1"}})()

    monkeypatch.setattr("factory.dataset.mcp.operational.dataset_submit_generation", submit)
    mcp = ToolCatalog("dataset-test")
    register(mcp, tmp_path)
    tool = asyncio.run(mcp.get_tool("dataset_submit_generation"))
    result = tool.fn({
        "recipe_uri": "recipe://local/pass-through@1", "recipe_digest": "a" * 64,
        "context_snapshot_uri": "file:///context", "context_snapshot_digest": "b" * 64,
        "tool_schema_snapshot_uri": "file:///tools", "tool_schema_snapshot_digest": "c" * 64,
        "input_artifact_uris": ["file:///decoded", "file:///environment"],
        "input_artifact_digests": ["d" * 64, "e" * 64],
        "input_artifact_roles": ["decoded_can", "environment_context"],
    }).data.root
    assert result == {"job_id": "job-1"}
    assert [item.artifact_role for item in captured[0].input_artifacts] == [
        "decoded_can", "environment_context",
    ]


def test_mcp_allowed_local_roots_propagate_into_typed_request(tmp_path, monkeypatch):
    captured = []

    def submit(request, _storage_root):
        captured.append(request)
        return type("Receipt", (), {"model_dump": lambda self, mode: {"job_id": "job-1"}})()

    monkeypatch.setattr("factory.dataset.mcp.operational.dataset_submit_generation", submit)
    mcp = ToolCatalog("dataset-test")
    register(mcp, tmp_path)
    tool = asyncio.run(mcp.get_tool("dataset_submit_generation"))
    result = tool.fn({
        "recipe_uri": "recipe://local/pass-through@1", "recipe_digest": "a" * 64,
        "context_snapshot_uri": "file:///context", "context_snapshot_digest": "b" * 64,
        "tool_schema_snapshot_uri": "file:///tools", "tool_schema_snapshot_digest": "c" * 64,
        "allowed_local_roots": [str(tmp_path)],
    })

    assert result.ok is True
    assert captured[0].allowed_local_roots == (tmp_path,)


def test_context_routes_merge_overrides_and_reject_conflicts(tmp_path: Path):
    decoded = tmp_path / "decoded.jsonl"
    context = tmp_path / "context.jsonl"
    decoded.write_text("{}\n")
    context.write_text("{}\n")
    inputs = [_input(decoded, "decoded_can"), _input(context, "environment_context")]
    request = _request(
        tmp_path, "recipe://local/context-augment@1", inputs,
        {"stage_overrides": {"context_augment": {
            "merge_strategy": "last_known", "max_time_delta_s": 42,
        }}, "vehicle_id": "provenance-only"},
    )
    cfg = resolve_recipe(request).stages[0].config
    assert cfg["input_uri"] == decoded.as_uri()
    assert cfg["context_uri"] == context.as_uri()
    assert cfg["merge_strategy"] == "last_known"
    assert cfg["max_time_delta_s"] == 42
    assert "vehicle_id" not in cfg

    conflict = _request(
        tmp_path, "recipe://local/context-augment@1", inputs,
        {"stage_overrides": {"context_augment": {"input_uri": context.as_uri()}}},
    )
    with pytest.raises(ValueError, match="routing conflicts"):
        resolve_recipe(conflict)

    ambiguous = _request(
        tmp_path, "recipe://local/context-augment@1",
        [*inputs, _input(context, "decoded_can")], {},
    )
    with pytest.raises(ValueError, match="Ambiguous artifact role"):
        resolve_recipe(ambiguous)


def test_builtin_correlate_defaults_are_numeric_and_canonical(tmp_path: Path):
    augmented = tmp_path / "augmented.jsonl"
    augmented.write_text("{}\n")
    request = _request(
        tmp_path, "recipe://local/context-correlate@1",
        [_input(augmented, "context_augmented_can")],
        {"stage_overrides": {"context_correlate": {
            "method": "spearman", "min_correlation": 0.1,
        }}},
    )
    cfg = resolve_recipe(request).stages[0].config
    assert cfg["input_uri"] == augmented.as_uri()
    assert cfg["method"] == "spearman"
    assert len(cfg["failure_modes"]) == 8
    assert "road_type" not in cfg["context_features"]
