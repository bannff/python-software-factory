"""Tests for versioned recipe resolution and local stage composition."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from factory.dataset.runtime.contracts import (
    DatasetExecutionPolicy,
    DatasetGenerationRequest,
    DatasetInputRef,
    DatasetJobStatus,
    DatasetProvenanceRecord,
    DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.adapters.checkpoints import LocalStageCheckpointStore
from factory.dataset.runtime.local import LocalDatasetMaterializer, LocalDatasetStore
from factory.dataset.runtime.quality import evaluate_quality
from factory.dataset.runtime.recipe import load_records, path_from_uri, records_content, resolve_recipe
import pytest


def _snapshot(root: Path, label: str, content: bytes) -> DatasetSnapshotRef:
    snapshot_dir = root / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    path = snapshot_dir / f"{label}-{digest}.json"
    if not path.exists():
        path.write_bytes(content)
        path.chmod(0o444)
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _tool_snapshot(root: Path, allowed_tools: list[str] | None = None) -> DatasetToolSchemaSnapshotRef:
    allowed_tools = allowed_tools or []
    content = json.dumps({"allowed_tools": allowed_tools}, sort_keys=True).encode()
    snapshot = _snapshot(root, "tool-schema", content)
    return DatasetToolSchemaSnapshotRef(uri=snapshot.uri, digest=snapshot.digest, allowed_tools=allowed_tools)


def test_recipe_executes_stage_and_materializes_training_view(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"hello"}]}\n')
    recipe = tmp_path / "recipe.json"
    recipe_content = json.dumps(
        {
            "version": "test-recipe-v1",
            "stages": [{"name": "local-validate", "config": {"marker": "tested"}}],
        },
        separators=(",", ":"),
    ).encode()
    recipe.write_bytes(recipe_content)

    def local_validate_stage(records, config):
        assert config == {"marker": "tested"}
        return records

    store = LocalDatasetStore(tmp_path / "store")
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(recipe_content).hexdigest(),
        input_artifacts=[
            DatasetInputRef(
                uri=source.as_uri(),
                digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        ],
        requested_views=["sft"],
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"recipe-test"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
    )
    status = DatasetJobStatus(
        job_id="job-1",
        status="running",
        submitted_at=datetime.now(UTC),
        request=request,
    )
    store.save_job(status)

    artifact = LocalDatasetMaterializer(store, {"local-validate": _Stage(local_validate_stage)}).materialize(status)

    assert artifact.available_views == ["sft"]
    assert artifact.training_uri is not None
    assert artifact.dataset_uri.endswith(".jsonl")
    assert (store.root / "checkpoints" / "job-1").exists()


def test_file_uri_decodes_escaped_paths(tmp_path: Path) -> None:
    path = tmp_path / "records with spaces.jsonl"
    path.write_text("{}")
    assert path_from_uri(path.as_uri()) == path


def test_recipe_execution_resumes_from_existing_checkpoint_without_rerunning_completed_stage(
    tmp_path: Path,
) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"hello"}]}\n')
    recipe = tmp_path / "recipe.json"
    recipe_content = json.dumps(
        {
            "version": "test-recipe-v1",
            "stages": [
                {"name": "context_ingest", "config": {"marker": "checkpointed"}},
                {"name": "context_augment", "config": {}},
            ],
        },
        separators=(",", ":"),
    ).encode()
    recipe.write_bytes(recipe_content)

    store = LocalDatasetStore(tmp_path / "store")
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(recipe_content).hexdigest(),
        input_artifacts=[
            DatasetInputRef(
                uri=source.as_uri(),
                digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        ],
        requested_views=["sft"],
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"recipe-test"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
    )
    status = DatasetJobStatus(
        job_id="job-1",
        status="running",
        submitted_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        request=request,
    )
    store.save_job(status)

    records = load_records(request)
    checkpoint_store = LocalStageCheckpointStore(store.root / "checkpoints" / status.job_id)
    checkpoint = checkpoint_store.save(
        stage_name="context_ingest",
        stage_index=0,
        input_digest=hashlib.sha256(records_content(records)).hexdigest(),
        records=records,
        schema_version=resolve_recipe(request).schema_version,
        adapter_version="checkpoint-revision",
        config={"marker": "checkpointed"},
        context_snapshot_digest=request.context_snapshot.digest,
        tool_schema_snapshot_digest=request.tool_schema_snapshot.digest,
        provenance=DatasetProvenanceRecord(
            materializer="local-recipe", job_id=status.job_id,
        ),
        quality_results=evaluate_quality(records),
    )
    legacy_checkpoint = checkpoint.model_copy(
        update={"checkpoint_digest": None},
    )
    checkpoint_path = next(checkpoint_store.root.glob("*.checkpoint.json"))
    checkpoint_path.chmod(0o644)
    checkpoint_path.write_text(
        legacy_checkpoint.model_dump_json(exclude_none=True),
    )
    checkpoint_path.chmod(0o444)

    def fail_if_called(records, config):
        raise AssertionError("checkpointed stage should not run again")

    context_ingest_stage = _Stage(fail_if_called, name="context_ingest")
    context_augment_stage = _Stage(lambda records, config: records, name="context_augment")

    artifact = LocalDatasetMaterializer(
        store,
        {
            "context_ingest": context_ingest_stage,
            "context_augment": context_augment_stage,
        },
    ).materialize(status)

    assert context_ingest_stage.calls == 0
    assert context_augment_stage.calls == 1
    assert artifact.training_uri is not None
    assert store.get_job(status.job_id) is not None


def test_cancellation_prevents_later_stages_and_artifact_completion(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"hello"}]}\n')
    recipe = tmp_path / "recipe.json"
    recipe_content = json.dumps(
        {
            "version": "test-recipe-v1",
            "stages": [
                {"name": "context_ingest", "config": {}},
                {"name": "context_augment", "config": {}},
            ],
        },
        separators=(",", ":"),
    ).encode()
    recipe.write_bytes(recipe_content)

    store = LocalDatasetStore(tmp_path / "store")
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(recipe_content).hexdigest(),
        input_artifacts=[
            DatasetInputRef(
                uri=source.as_uri(),
                digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        ],
        requested_views=["sft"],
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"cancel-test"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
    )
    status = DatasetJobStatus(
        job_id="job-2",
        status="running",
        submitted_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        request=request,
    )
    store.save_job(status)

    def cancel_after_stage(records, config):
        store.cancel_job(status.job_id, "cancelled by test")
        return records

    context_ingest_stage = _Stage(cancel_after_stage, name="context_ingest")
    context_augment_stage = _Stage(lambda records, config: records, name="context_augment")

    with pytest.raises(RuntimeError, match="running"):
        LocalDatasetMaterializer(
            store,
            {
                "context_ingest": context_ingest_stage,
                "context_augment": context_augment_stage,
            },
        ).materialize(status)

    cancelled = store.get_job(status.job_id)
    assert cancelled is not None
    assert cancelled.status == "failed"
    assert cancelled.error == "cancelled by test"
    assert context_augment_stage.calls == 0


@pytest.mark.parametrize("uri", ["file:relative.jsonl", "file:///tmp/a.jsonl?x=1", "file:///tmp/%2e%2e/a.jsonl"])
def test_invalid_file_uri_forms_are_rejected(uri: str) -> None:
    with pytest.raises(ValueError, match="Only local file URIs|Path traversal"):
        path_from_uri(uri)


def test_empty_file_recipe_is_rejected(tmp_path: Path) -> None:
    recipe = tmp_path / "empty-recipe.json"
    content = json.dumps({"version": "empty", "stages": []}).encode()
    recipe.write_bytes(content)
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(content).hexdigest(),
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"empty-recipe-test"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
    )

    try:
        resolve_recipe(request)
    except ValueError as error:
        assert "Invalid dataset recipe" in str(error)
    else:
        raise AssertionError("empty recipe should not resolve")


def test_multi_view_request_materializes_all_views(tmp_path: Path) -> None:
    source = tmp_path / "records.jsonl"
    source.write_text('{"messages":[{"role":"user","content":"hello"}]}\n')
    recipe = tmp_path / "recipe.json"
    recipe_content = json.dumps(
        {
            "version": "test-recipe-v1",
            "stages": [{"name": "local-validate", "config": {}}],
        },
        separators=(",", ":"),
    ).encode()
    recipe.write_bytes(recipe_content)

    store = LocalDatasetStore(tmp_path / "store")
    request = DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(recipe_content).hexdigest(),
        input_artifacts=[
            DatasetInputRef(
                uri=source.as_uri(),
                digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            )
        ],
        requested_views=["sft", "dpo"],
        context_snapshot=_snapshot(tmp_path, "context", b'{"source":"multi-view-test"}'),
        tool_schema_snapshot=_tool_snapshot(tmp_path),
        execution_policy=DatasetExecutionPolicy(),
    )
    status = DatasetJobStatus(
        job_id="job-multi",
        status="running",
        submitted_at=datetime.now(UTC),
        request=request,
    )
    store.save_job(status)

    def local_validate_stage(records, config):
        return records

    artifact = LocalDatasetMaterializer(store, {"local-validate": _Stage(local_validate_stage)}).materialize(status)

    assert artifact.available_views == ["sft", "dpo"]
    assert "sft" in artifact.view_schema_versions
    assert "dpo" in artifact.view_schema_versions
    assert artifact.training_uri is not None

    bundle_dir = store.artifacts_dir / "job-multi"
    view_files = list(bundle_dir.glob("view-*.jsonl"))
    assert len(view_files) == 2

    from factory.dataset.runtime.local import _file_uri
    from factory.dataset.runtime.contracts import DatasetManifest

    manifest_path = Path(artifact.manifest_uri.removeprefix("file://"))
    manifest = DatasetManifest.model_validate_json(manifest_path.read_bytes())
    assert manifest.training_views == ["sft", "dpo"]
    assert manifest.view_schema_versions == {"sft": "1.0", "dpo": "1.0"}

    first_view_matches = list(bundle_dir.glob("view-sft-*.jsonl"))
    assert len(first_view_matches) == 1
    assert artifact.training_uri == _file_uri(first_view_matches[0])


class _Stage:
    def __init__(self, function, name: str = "local-validate", stage_version: str = "test-revision"):
        self.function = function
        self.name = name
        self.stage_version = stage_version
        self.calls = 0

    def execute(self, records, config=None):
        self.calls += 1
        return self.function(records, config or {})