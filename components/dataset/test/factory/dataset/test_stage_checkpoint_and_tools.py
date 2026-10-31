"""Checkpoint immutability and APIGenMT tool-schema-snapshot enforcement.

Split from test_stage_adapters.py (LOC tenet).
"""

from __future__ import annotations

import hashlib
import json

import pytest

from factory.dataset.runtime.adapters.checkpoints import LocalStageCheckpointStore
from factory.dataset.runtime.adapters.generation_stages import APIGenMTStageAdapter
from factory.dataset.runtime.contracts import (
    DatasetProvenanceRecord,
    DatasetQualityResults,
    DatasetToolSchemaSnapshotRef,
)


def _tool_schema_snapshot(tmp_path, allowed_tools: list[str]) -> DatasetToolSchemaSnapshotRef:
    content = json.dumps({"allowed_tools": allowed_tools}, sort_keys=True).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = tmp_path / f"tool-schema-{digest}.json"
    if not path.exists():
        path.write_bytes(content)
        path.chmod(0o444)
    return DatasetToolSchemaSnapshotRef(uri=path.as_uri(), digest=digest, allowed_tools=allowed_tools)


def test_stage_checkpoint_is_immutable_and_schema_validated(tmp_path) -> None:
    store = LocalStageCheckpointStore(tmp_path)
    records = [{"messages": [{"role": "user", "content": "hello"}]}]

    checkpoint = store.save(
        stage_name="s2m",
        stage_index=0,
        input_digest="a" * 64,
        records=records,
        schema_version="1.0",
        adapter_version="factory-native-1",
        context_snapshot_digest="a" * 64,
        tool_schema_snapshot_digest="b" * 64,
        provenance=DatasetProvenanceRecord(materializer="local-test", job_id="job-1"),
        quality_results=DatasetQualityResults(checks={"schema": "passed"}),
    )

    assert checkpoint.record_count == 1
    assert checkpoint.output_uri.startswith("file://")
    with pytest.raises(ValueError, match="different content"):
        store.save(
            stage_name="s2m",
            stage_index=0,
            input_digest="b" * 64,
            records=records,
            schema_version="1.0",
            adapter_version="factory-native-1",
            context_snapshot_digest="a" * 64,
            tool_schema_snapshot_digest="b" * 64,
            provenance=DatasetProvenanceRecord(materializer="local-test", job_id="job-1"),
            quality_results=DatasetQualityResults(checks={"schema": "passed"}),
        )


def test_apigenmt_requires_allowlisted_tools(tmp_path) -> None:
    adapter = APIGenMTStageAdapter(lambda records, **kwargs: records)
    snapshot = _tool_schema_snapshot(tmp_path, ["safe_tool"])

    with pytest.raises(ValueError, match="does not allow tools"):
        list(
            adapter.execute(
                [{"messages": [{"role": "user", "content": "input"}]}],
                {
                    "tools": [{"name": "unsafe_tool", "parameters": {}}],
                    "tool_schema_snapshot": snapshot,
                },
            )
        )


def test_apigenmt_rejects_missing_tool_schema_snapshot() -> None:
    adapter = APIGenMTStageAdapter(lambda records, **kwargs: records)

    with pytest.raises(ValueError, match="requires an immutable tool schema snapshot"):
        list(adapter.execute([{"messages": [{"role": "user", "content": "input"}]}], {"tools": []}))
