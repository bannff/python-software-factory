"""Regression coverage for ScenarioPack request and checkpoint integrity."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.dataset.interface import dataset_publish_scenario_pack
from factory.dataset.runtime.adapters.checkpoints import LocalStageCheckpointStore
from factory.dataset.runtime.adapters.scenario_generate import ScenarioGenerateStageAdapter
from factory.dataset.runtime.contracts import DatasetQualityResults
from factory.dataset.runtime.recipe import resolve_recipe
from factory.dataset.runtime.scenario_errors import ScenarioGenerationError
from factory.dataset.runtime.scenario_models import ScenarioPackGenerationInput
from factory.dataset.runtime.stage_runner import run_stage_loop

from .scenario_fixtures import draft
from .test_scenario_generation import _request


def _run_once(tmp_path: Path):
    root = tmp_path / "store"
    published = dataset_publish_scenario_pack(draft(), root)
    request = _request(tmp_path, published.ref)
    recipe = resolve_recipe(request)
    checkpoints = LocalStageCheckpointStore(tmp_path / "checkpoints")
    result = run_stage_loop(
        recipe, request, [],
        {"scenario_generate": ScenarioGenerateStageAdapter(root)},
        checkpoints, {}, "job-integrity",
    )
    return root, request, recipe, checkpoints, result[-1][0]


def test_external_recipe_pack_divergence_fails_before_checkpoint(tmp_path: Path) -> None:
    root = tmp_path / "store"
    first = dataset_publish_scenario_pack(draft(), root)
    second = dataset_publish_scenario_pack(
        draft().model_copy(update={"identity": "other-pack"}), root,
    )
    second_generation = ScenarioPackGenerationInput(
        scenario_pack=second.ref,
        generator_adapter="dataset.deterministic-template",
        generator_version="1.0",
        seed=41,
    )
    recipe_path = tmp_path / "external-recipe.json"
    recipe_path.write_text(json.dumps({
        "version": "external-scenario-v1",
        "record_schema": "generic",
        "stages": [{
            "name": "scenario_generate",
            "config": {"scenario_generation": second_generation.model_dump(mode="json")},
        }],
    }))
    request = _request(tmp_path, first.ref).model_copy(update={
        "recipe_uri": recipe_path.as_uri(),
        "recipe_digest": hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
    })
    checkpoints = LocalStageCheckpointStore(tmp_path / "external-checkpoints")
    with pytest.raises(ScenarioGenerationError, match="submitted request"):
        run_stage_loop(
            resolve_recipe(request), request, [],
            {"scenario_generate": ScenarioGenerateStageAdapter(root)},
            checkpoints, {}, "job-external",
        )
    assert not list(checkpoints.root.iterdir())


def test_resume_recomputes_quality_metadata(tmp_path: Path) -> None:
    root, request, recipe, checkpoints, checkpoint = _run_once(tmp_path)
    tampered = checkpoint.model_copy(update={
        "quality_results": DatasetQualityResults(checks={"forged": "passed"}),
    })
    with pytest.raises(ValueError, match="quality results"):
        run_stage_loop(
            recipe, request, [],
            {"scenario_generate": ScenarioGenerateStageAdapter(root)},
            checkpoints, {0: tampered}, "job-integrity",
        )


def test_resume_rejects_output_outside_checkpoint_store(tmp_path: Path) -> None:
    root, request, recipe, checkpoints, checkpoint = _run_once(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(Path(checkpoint.output_uri.removeprefix("file://")).read_bytes())
    tampered = checkpoint.model_copy(update={"output_uri": outside.as_uri()})
    with pytest.raises(ValueError, match="outside its immutable store"):
        run_stage_loop(
            recipe, request, [],
            {"scenario_generate": ScenarioGenerateStageAdapter(root)},
            checkpoints, {0: tampered}, "job-integrity",
        )
