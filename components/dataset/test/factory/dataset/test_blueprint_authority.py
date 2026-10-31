"""Submission and worker authority regressions for the gated scenario route."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from factory.dataset.interface import (
    dataset_get_job, dataset_materialize_blueprint, dataset_submit_generation,
)
from factory.dataset.runtime.local import LocalDatasetStore
from factory.dataset.runtime.materializer import LocalDatasetMaterializer
from factory.dataset.server import create_mcp_server

from .blueprint_fixtures import blueprint, configure


def _queued_request(tmp_path: Path, monkeypatch):
    root = tmp_path / "bound-store"
    value = blueprint(root)
    approval = configure(monkeypatch, value)[
        f"{value.identity}:{value.generation_seed}"
    ]
    monkeypatch.setattr(
        "factory.dataset.interface.LocalDatasetExecutor.submit", lambda *_: None,
    )
    submitted = dataset_materialize_blueprint(value, approval, root)
    status = dataset_get_job(submitted.job_id, root)
    assert status is not None
    return root, status.request


@pytest.mark.asyncio
async def test_unbound_public_and_legacy_mcp_scenario_requests_reject(
    tmp_path: Path, monkeypatch,
) -> None:
    _, request = _queued_request(tmp_path, monkeypatch)
    unbound = request.model_copy(update={
        "blueprint_binding": None,
        "approval_binding": None,
        "idempotency_key": "unbound-scenario",
    })
    public_root = tmp_path / "public-unbound"
    effects: list[str] = []
    monkeypatch.setattr(
        "factory.dataset.interface.LocalDatasetExecutor.submit",
        lambda job_id: effects.append(job_id),
    )
    with pytest.raises(ValueError, match="blueprint and approval bindings"):
        dataset_submit_generation(unbound, public_root)
    assert not public_root.exists()

    generation = unbound.scenario_generation
    assert generation is not None
    mcp_root = tmp_path / "mcp-unbound"
    server = create_mcp_server(mcp_root)
    arguments = {
        "recipe_uri": unbound.recipe_uri,
        "recipe_digest": unbound.recipe_digest,
        "context_snapshot_uri": unbound.context_snapshot.uri,
        "context_snapshot_digest": unbound.context_snapshot.digest,
        "tool_schema_snapshot_uri": unbound.tool_schema_snapshot.uri,
        "tool_schema_snapshot_digest": unbound.tool_schema_snapshot.digest,
        "input_artifact_uris": [item.uri for item in unbound.input_artifacts],
        "input_artifact_digests": [item.digest for item in unbound.input_artifacts],
        "input_artifact_roles": [item.artifact_role for item in unbound.input_artifacts],
        "scenario_pack_identity": generation.scenario_pack.identity,
        "scenario_pack_version": generation.scenario_pack.version,
        "scenario_pack_uri": generation.scenario_pack.uri,
        "scenario_pack_digest": generation.scenario_pack.digest,
        "generator_adapter": generation.generator_adapter,
        "generator_version": generation.generator_version,
        "generation_seed": generation.seed,
    }
    result = await server.call_tool("dataset_submit_generation", arguments)
    payload = result.structured_content
    assert payload["ok"] is False
    assert payload["data"] is None
    assert payload["error"] == "tool_execution_failed"
    assert not list((mcp_root / "jobs").glob("*.json"))
    assert effects == []


def test_unrelated_legacy_request_remains_compatible(tmp_path: Path, monkeypatch) -> None:
    _, request = _queued_request(tmp_path, monkeypatch)
    recipe_uri = "recipe://local/pass-through@1"
    legacy = request.model_copy(update={
        "recipe_uri": recipe_uri,
        "recipe_digest": hashlib.sha256(recipe_uri.encode()).hexdigest(),
        "input_artifacts": [],
        "scenario_generation": None,
        "blueprint_binding": None,
        "approval_binding": None,
        "idempotency_key": "legacy-pass-through",
    })
    root = tmp_path / "legacy-store"
    receipt = dataset_submit_generation(legacy, root)
    assert dataset_get_job(receipt.job_id, root) is not None


@pytest.mark.parametrize(
    "authority_env",
    ["DATASET_HUMAN_APPROVALS_JSON", "DATASET_QUALITY_POLICY_REFS_JSON"],
)
def test_authority_mutation_after_enqueue_rejects_before_stage_effects(
    tmp_path: Path, monkeypatch, authority_env: str,
) -> None:
    root, request = _queued_request(tmp_path, monkeypatch)
    status = next(
        item for item in (dataset_get_job(path.stem, root)
                          for path in (root / "jobs").glob("*.json"))
        if item is not None and item.request == request
    )
    running = LocalDatasetStore(root).claim_job(status.job_id)
    monkeypatch.setenv(authority_env, "[]")

    class StageMustNotRun:
        calls = 0

        def execute(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("stage effect executed before authority validation")

    stage = StageMustNotRun()
    with pytest.raises(ValueError, match="approval|quality-policy"):
        LocalDatasetMaterializer(
            LocalDatasetStore(root), {"scenario_generate": stage},
        ).materialize(running)
    assert stage.calls == 0
    assert not list((root / "checkpoints").glob("**/*"))
    assert not list((root / "artifacts").glob("**/*"))
    assert not list((root / "manifests").glob("**/*"))


def test_exact_approval_binding_mismatch_rejects_before_job_lookup(
    tmp_path: Path, monkeypatch,
) -> None:
    root, request = _queued_request(tmp_path, monkeypatch)
    assert request.approval_binding is not None
    approval = request.approval_binding.approval.model_copy(update={"digest": "0" * 64})
    authority = request.approval_binding.model_copy(update={"approval": approval})
    divergent = request.model_copy(update={
        "approval_binding": authority,
        "idempotency_key": "mismatched-authority",
    })
    before = set((root / "jobs").glob("*.json"))
    with pytest.raises(ValueError, match="approval"):
        dataset_submit_generation(divergent, root)
    assert set((root / "jobs").glob("*.json")) == before
