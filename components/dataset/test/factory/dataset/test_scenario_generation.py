"""ScenarioPack recipe generation, checkpoint, and manifest lineage tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from factory.dataset.interface import (
    dataset_get_scenario_pack, dataset_publish_scenario_pack,
)
from factory.dataset.runtime.adapters.checkpoints import LocalStageCheckpointStore
from factory.dataset.runtime.adapters.scenario_generate import ScenarioGenerateStageAdapter
from factory.dataset.runtime.checkpoint_integrity import checkpoint_metadata_digest
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest, DatasetInputRef, DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import LocalDatasetStore
from factory.dataset.runtime.materializer import LocalDatasetMaterializer
from factory.dataset.runtime.recipe import resolve_recipe
from factory.dataset.runtime.scenario_errors import ScenarioGenerationError
from factory.dataset.runtime.scenario_generation import generate_episodes
from factory.dataset.runtime.scenario_models import ScenarioPackGenerationInput
from factory.dataset.runtime.stage_runner import run_stage_loop

from .scenario_fixtures import draft


def _snapshot(tmp_path: Path, name: str) -> DatasetSnapshotRef:
    path = tmp_path / f"{name}.json"
    path.write_text("{}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return DatasetSnapshotRef(uri=path.as_uri(), digest=digest)


def _request(tmp_path: Path, ref, *, version: str = "1.0") -> DatasetGenerationRequest:
    uri = "recipe://local/scenario-generate@1"
    return DatasetGenerationRequest(
        recipe_uri=uri, recipe_digest=hashlib.sha256(uri.encode()).hexdigest(),
        input_artifacts=[DatasetInputRef(
            uri=ref.uri, digest=ref.digest, artifact_role="scenario_pack",
        )],
        context_snapshot=_snapshot(tmp_path, "context"),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            **_snapshot(tmp_path, "tools").model_dump(), allowed_tools=[],
        ),
        scenario_generation=ScenarioPackGenerationInput(
            scenario_pack=ref, generator_adapter="dataset.deterministic-template",
            generator_version=version, seed=41,
        ),
    )


def test_generation_is_complete_deterministic_and_ordinal_bound(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    pack = dataset_get_scenario_pack(published.ref, root)  # type: ignore[arg-type]
    request = _request(tmp_path, published.ref).scenario_generation
    assert request is not None
    first, lineage = generate_episodes(pack, request)
    second, second_lineage = generate_episodes(pack, request)
    assert first == second
    assert lineage == second_lineage
    assert len(first) == 8
    assert len({(r["scenario_id"], r["outcome_id"], r["ordinal"]) for r in first}) == 8
    groups_by_scenario: dict[str, set[str]] = {}
    for record in first:
        groups_by_scenario.setdefault(record["scenario_id"], set()).add(
            record["split_group"]
        )
    assert all(len(groups) == 1 for groups in groups_by_scenario.values())
    assert len({next(iter(groups)) for groups in groups_by_scenario.values()}) == 2
    assert all(item.episode_digest for item in lineage.episodes)


def test_generation_rejects_adapter_version_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    pack = dataset_get_scenario_pack(published.ref, root)  # type: ignore[arg-type]
    generation = _request(tmp_path, published.ref, version="2.0").scenario_generation
    with pytest.raises(ScenarioGenerationError, match="generation rule"):
        generate_episodes(pack, generation)  # type: ignore[arg-type]


def test_typed_recipe_routing_and_checkpoint_resume_preserve_lineage(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    request = _request(tmp_path, published.ref)
    recipe = resolve_recipe(request)
    assert recipe.stages[0].name == "scenario_generate"
    assert recipe.stages[0].config["scenario_generation"]["scenario_pack"]["digest"] == published.ref.digest
    checkpoint_store = LocalStageCheckpointStore(tmp_path / "checkpoints")
    first = run_stage_loop(
        recipe, request, [], {"scenario_generate": ScenarioGenerateStageAdapter(root)},
        checkpoint_store, {}, "job-1",
    )
    checkpoint = first[-1][0]
    resumed = run_stage_loop(
        recipe, request, [], {"scenario_generate": ScenarioGenerateStageAdapter(root)},
        checkpoint_store, {0: checkpoint}, "job-1",
    )
    assert checkpoint.scenario_lineage is not None
    assert resumed[-1][0].scenario_lineage == checkpoint.scenario_lineage
    assert resumed[0] == first[0]


def test_unbound_materializer_rejects_before_lineage_effects(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    request = _request(tmp_path, published.ref)
    store = LocalDatasetStore(root)
    receipt, _ = store.create_or_get_job(request)
    running = store.claim_job(receipt.job_id)

    with pytest.raises(ValueError, match="blueprint and approval bindings"):
        LocalDatasetMaterializer(
            store, {"scenario_generate": ScenarioGenerateStageAdapter(root)},
        ).materialize(running)
    assert not list(store.artifacts_dir.iterdir())
    assert not list(store.manifests_dir.iterdir())
    assert not list((root / "checkpoints").glob("**/*"))


def test_resume_rejects_tampered_episode_lineage(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    request = _request(tmp_path, published.ref)
    recipe = resolve_recipe(request)
    checkpoint_store = LocalStageCheckpointStore(tmp_path / "checkpoints")
    result = run_stage_loop(
        recipe, request, [], {"scenario_generate": ScenarioGenerateStageAdapter(root)},
        checkpoint_store, {}, "job-tamper",
    )
    checkpoint = result[-1][0]
    assert checkpoint.scenario_lineage is not None
    episodes = list(checkpoint.scenario_lineage.episodes)
    episodes[0] = episodes[0].model_copy(update={"episode_digest": "0" * 64})
    bad_lineage = checkpoint.scenario_lineage.model_copy(update={"episodes": tuple(episodes)})
    tampered = checkpoint.model_copy(update={"scenario_lineage": bad_lineage})
    tampered = tampered.model_copy(update={
        "checkpoint_digest": checkpoint_metadata_digest(tampered),
    })
    with pytest.raises(ScenarioGenerationError, match="lineage"):
        run_stage_loop(
            recipe, request, [], {"scenario_generate": ScenarioGenerateStageAdapter(root)},
            checkpoint_store, {0: tampered}, "job-tamper",
        )


def test_resume_rejects_provenance_only_lineage_tamper(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    request = _request(tmp_path, published.ref)
    recipe = resolve_recipe(request)
    checkpoint_store = LocalStageCheckpointStore(tmp_path / "checkpoints-provenance")
    result = run_stage_loop(
        recipe, request, [], {"scenario_generate": ScenarioGenerateStageAdapter(root)},
        checkpoint_store, {}, "job-provenance-tamper",
    )
    checkpoint = result[-1][0]
    assert checkpoint.scenario_lineage is not None
    episodes = list(checkpoint.scenario_lineage.episodes)
    episodes[0] = episodes[0].model_copy(update={"claim_ids": ("forged-claim",)})
    bad_lineage = checkpoint.scenario_lineage.model_copy(update={
        "episodes": tuple(episodes), "sources": (),
    })
    tampered = checkpoint.model_copy(update={"scenario_lineage": bad_lineage})
    tampered = tampered.model_copy(update={
        "checkpoint_digest": checkpoint_metadata_digest(tampered),
    })
    with pytest.raises(ScenarioGenerationError, match="canonical pack"):
        run_stage_loop(
            recipe, request, [], {"scenario_generate": ScenarioGenerateStageAdapter(root)},
            checkpoint_store, {0: tampered}, "job-provenance-tamper",
        )
