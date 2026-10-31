"""Named-MCP blueprint materialization, replay, conflict, and lineage acceptance."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from factory.dataset.interface import (
    dataset_get_job,
    dataset_materialize_blueprint,
    dataset_submit_generation,
)
from factory.dataset.runtime.blueprint_codec import (
    approval_digest, blueprint_binding, blueprint_lineage, canonical_digest,
)
from factory.dataset.runtime.blueprint_models import (
    DatasetHumanApprovalRecord, DatasetHumanApprovalRef,
)
from factory.dataset.runtime.contracts import DatasetManifest
from factory.dataset.server import create_mcp_server

from .blueprint_fixtures import approval_for, blueprint, configure


def _payload(result) -> dict:
    structured = result.structured_content
    if structured and set(structured) == {"result"}:
        return structured["result"]
    if structured and structured.get("schema_version") == "v1":
        assert structured["ok"] is True, structured
        return structured["data"]
    assert structured is not None
    return structured


async def _terminal(server, job_id: str) -> dict:
    for _ in range(200):
        status = _payload(await server.call_tool(
            "dataset_get_job", {"job_id": job_id},
        ))
        if status is not None and status["status"] in {"completed", "failed"}:
            return status
        await asyncio.sleep(0.025)
    pytest.fail("dataset worker did not reach a terminal state")


@pytest.mark.asyncio
async def test_non_security_blueprint_materializes_through_named_mcp(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "store"
    value = blueprint(root)
    divergent = blueprint(root, seed=42)
    approvals = configure(monkeypatch, value, divergent)
    approval = approvals[f"{value.identity}:{value.generation_seed}"]
    divergent_approval = approvals[f"{divergent.identity}:{divergent.generation_seed}"]
    server = create_mcp_server(root)
    arguments = {
        "blueprint_json": value.model_dump_json(),
        "approval_id": approval.id,
        "approval_revision": approval.revision,
        "approval_digest": approval.digest,
    }

    validated = _payload(await server.call_tool(
        "dataset_validate_blueprint", {"blueprint_json": value.model_dump_json()},
    ))
    first = _payload(await server.call_tool("dataset_materialize_blueprint", arguments))
    completed = await _terminal(server, first["job_id"])
    replay = _payload(await server.call_tool("dataset_materialize_blueprint", arguments))
    replay_status = _payload(await server.call_tool(
        "dataset_get_job", {"job_id": replay["job_id"]},
    ))
    before_conflict = {path.relative_to(root) for path in root.rglob("*")}
    conflict = _payload(await server.call_tool("dataset_materialize_blueprint", {
        "blueprint_json": divergent.model_dump_json(),
        "approval_id": divergent_approval.id,
        "approval_revision": divergent_approval.revision,
        "approval_digest": divergent_approval.digest,
    }))
    artifact_payload = _payload(await server.call_tool(
        "dataset_get_artifact", {"job_id": first["job_id"]},
    ))
    manifest_payload = _payload(await server.call_tool(
        "dataset_resolve_artifact", {"dataset_uri": artifact_payload["dataset_uri"]},
    ))

    assert validated["status"] == "validated"
    assert validated["recipe_uri"] == "recipe://local/scenario-generate@1"
    assert validated["stage_names"] == ["scenario_generate"]
    assert first["status"] == "queued"
    assert completed["status"] == "completed", completed["error"]
    assert replay["job_id"] == first["job_id"]
    assert replay["blueprint"] == first["blueprint"]
    assert replay_status["artifact"] == completed["artifact"]
    assert conflict["status"] == "conflict"
    assert conflict["conflict"]["existing_digest"] == first["blueprint"]["digest"]
    assert {path.relative_to(root) for path in root.rglob("*")} == before_conflict

    manifest = DatasetManifest.model_validate(manifest_payload)
    binding = blueprint_binding(value)
    assert artifact_payload == completed["artifact"]
    assert manifest.blueprint_binding == binding
    assert manifest.approval_binding == dataset_get_job(first["job_id"], root).request.approval_binding
    assert manifest.blueprint_lineage == blueprint_lineage(value, binding)
    assert manifest.recipe_uri == "recipe://local/scenario-generate@1"
    assert manifest.recipe_digest == value.recipe.digest
    assert tuple(item.stage_name for item in manifest.stage_lineage) == (value.stages[0].id,)
    assert manifest.schema_version == value.output_schema.version
    assert manifest.input_artifacts[0].digest == value.source_evidence[0].artifact.digest
    assert manifest.blueprint_lineage.capabilities == value.capabilities
    assert manifest.blueprint_lineage.binding.quality_policy == value.quality_policy


@pytest.mark.parametrize("failure", ["unknown", "digest", "blueprint"])
def test_approval_references_fail_closed(
    tmp_path: Path, monkeypatch, failure: str,
) -> None:
    root = tmp_path / "store"
    value = blueprint(root)
    other = blueprint(root, seed=42, identity="other-blueprint")
    approvals = configure(monkeypatch, value, other)
    correct = approvals[f"{value.identity}:{value.generation_seed}"]
    if failure == "unknown":
        candidate = correct.model_copy(update={"id": "missing"})
    elif failure == "digest":
        candidate = correct.model_copy(update={"digest": "0" * 64})
    else:
        candidate = approvals[f"{other.identity}:{other.generation_seed}"]
    with pytest.raises(ValueError, match="approval|bound"):
        dataset_materialize_blueprint(value, candidate, root)
    assert not list((root / "blueprints" / "sha256").glob("*.json"))
    assert not list((root / "jobs").glob("*.json"))


def test_approval_quality_policy_binding_fails_closed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "store"
    value = blueprint(root)
    configure(monkeypatch, value)
    wrong_policy = value.quality_policy.model_copy(update={"id": "other-policy"})
    record = DatasetHumanApprovalRecord(
        id="wrong-policy-approval", revision="1",
        blueprint_digest=canonical_digest(value), quality_policy=wrong_policy,
    )
    monkeypatch.setenv(
        "DATASET_HUMAN_APPROVALS_JSON",
        json.dumps([record.model_dump(mode="json")]),
    )
    candidate = DatasetHumanApprovalRef(
        id=record.id, revision=record.revision, digest=approval_digest(record),
    )
    with pytest.raises(ValueError, match="quality-policy"):
        dataset_materialize_blueprint(value, candidate, root)
    assert not list((root / "blueprints" / "sha256").glob("*.json"))
    assert not list((root / "jobs").glob("*.json"))


def test_divergent_idempotency_reuse_conflicts_before_effects(
    tmp_path: Path, monkeypatch,
) -> None:
    root = tmp_path / "store"
    value = blueprint(root)
    approval = configure(monkeypatch, value)[f"{value.identity}:{value.generation_seed}"]
    monkeypatch.setattr("factory.dataset.interface.LocalDatasetExecutor.submit", lambda *_: None)
    queued = dataset_materialize_blueprint(value, approval, root)
    assert queued.job_id is not None
    status = dataset_get_job(queued.job_id, root)
    assert status is not None
    divergent = status.request.model_copy(update={"requested_views": ["other"]})
    before = {path.relative_to(root) for path in root.rglob("*")}
    with pytest.raises(ValueError, match="authority bindings|idempotency key"):
        dataset_submit_generation(divergent, root)
    assert {path.relative_to(root) for path in root.rglob("*")} == before
