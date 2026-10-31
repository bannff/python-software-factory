from __future__ import annotations

import hashlib
import json

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.execution_manifest.artifact_models import (
    DefinitionArtifactRef, DefinitionDescriptor,
)
from factory.agent.runtime.execution_manifest.artifacts import (
    DATASET_MAX_BYTES, inline_max_bytes, resolve_manifest, store_manifest,
)
from factory.agent.runtime.execution_manifest.prepare import prepare_execution_manifest
from factory.agent.runtime.graph_contracts import GraphConfig


def _manifest():
    config = GraphConfig.model_validate({
        "id": "artifact", "name": "Artifact", "nodes": [{
            "id": "a", "type": "agent", "model": "model",
            "system_prompt": "hello", "tools": [], "skills": [],
        }], "entry_point": "a",
    })
    return prepare_execution_manifest(config, "task", {})


class FakeDatasetPort:
    def __init__(self, status: str = "published") -> None:
        self.status = status
        self.artifact: dict | None = None

    async def publish_definition(self, artifact_json: str) -> dict:
        self.artifact = json.loads(artifact_json)
        raw = artifact_json.encode()
        if self.status == "conflict":
            return {"status": "conflict", "conflict": {"reason": "different"}}
        return {"status": self.status, "ref": {
            "schema_name": self.artifact["schema_name"],
            "schema_version": self.artifact["schema_version"],
            "identity": self.artifact["identity"], "version": self.artifact["version"],
            "uri": "dataset://definition/artifact/1",
            "digest": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw),
        }}

    async def resolve_definition(self, reference: dict) -> dict:
        assert self.artifact is not None
        return self.artifact


@pytest.mark.asyncio
async def test_inline_and_dataset_reference_round_trip_same_manifest() -> None:
    manifest = _manifest()
    inline = await store_manifest(manifest, max_inline_bytes=DATASET_MAX_BYTES)
    assert (await resolve_manifest(inline)) == manifest
    port = FakeDatasetPort()
    referenced = await store_manifest(manifest, port, max_inline_bytes=1)
    assert referenced.reference is not None
    assert (await resolve_manifest(referenced, port)) == manifest


@pytest.mark.asyncio
async def test_publish_conflict_and_reference_tamper_fail_closed() -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="conflict"):
        await store_manifest(manifest, FakeDatasetPort("conflict"), max_inline_bytes=1)
    port = FakeDatasetPort()
    descriptor = await store_manifest(manifest, port, max_inline_bytes=1)
    bad = descriptor.reference.model_copy(update={"digest": "0" * 64})
    with pytest.raises(ValueError, match="bind"):
        await resolve_manifest(DefinitionDescriptor(reference=bad), port)


def test_inline_limit_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_EXECUTION_MANIFEST_INLINE_MAX_BYTES", "0")
    with pytest.raises(ValueError, match="positive"):
        inline_max_bytes()
    monkeypatch.setenv("AGENT_EXECUTION_MANIFEST_INLINE_MAX_BYTES", str(DATASET_MAX_BYTES + 1))
    with pytest.raises(ValueError, match="1 MiB"):
        inline_max_bytes()
