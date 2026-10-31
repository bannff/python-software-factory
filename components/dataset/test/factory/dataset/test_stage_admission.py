"""Dataset recipe admission regressions for deterministic materialization."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from factory.dataset.interface import dataset_get_job, dataset_submit_generation
from factory.dataset.runtime.contracts import (
    DatasetGenerationRequest, DatasetSnapshotRef, DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.recipe import resolve_recipe
from factory.dataset.runtime.stage_admission import RETAINED_STAGE_NAMES
from factory.dataset.runtime.stage_registry import default_stages


def _snapshot(root: Path, name: str) -> DatasetSnapshotRef:
    content = b"{}"
    path = root / f"{name}.json"
    path.write_bytes(content)
    return DatasetSnapshotRef(
        uri=path.as_uri(), digest=hashlib.sha256(content).hexdigest(),
    )


def _request(root: Path, recipe: Path, content: bytes) -> DatasetGenerationRequest:
    context = _snapshot(root, "context")
    tools = _snapshot(root, "tools")
    return DatasetGenerationRequest(
        recipe_uri=recipe.as_uri(),
        recipe_digest=hashlib.sha256(content).hexdigest(),
        context_snapshot=context,
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri=tools.uri, digest=tools.digest, allowed_tools=[],
        ),
    )


def test_default_stages_exclude_intelligent_stages_without_llm_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "factory.llm_gateway.interface", object())
    stages = default_stages(tmp_path)
    assert set(stages) == RETAINED_STAGE_NAMES
    assert not {"agentinstruct", "s2m", "apigenmt", "reviewinstruct"} & set(stages)


def test_external_disallowed_recipe_fails_before_durable_job_effects(tmp_path: Path) -> None:
    content = json.dumps({"version": "1", "stages": [
        {"name": "s2m"}, {"name": "agentinstruct"},
    ]}).encode()
    recipe = tmp_path / "disallowed.json"
    recipe.write_bytes(content)
    request = _request(tmp_path, recipe, content)
    root = tmp_path / "durable-store"

    with pytest.raises(
        ValueError, match=r"Disallowed dataset recipe stages: agentinstruct, s2m",
    ):
        dataset_submit_generation(request, root)

    assert not root.exists()


def test_retained_external_and_builtin_recipes_resolve_and_submit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b'{"version":"1","stages":[{"name":"local-validate"}]}'
    recipe = tmp_path / "deterministic.json"
    recipe.write_bytes(content)
    request = _request(tmp_path, recipe, content)
    submitted: list[str] = []
    monkeypatch.setattr(
        "factory.dataset.interface.LocalDatasetExecutor.submit",
        lambda _self, job_id: submitted.append(job_id),
    )

    assert [stage.name for stage in resolve_recipe(request).stages] == ["local-validate"]
    assert [stage.name for stage in resolve_recipe(request.model_copy(update={
        "recipe_uri": "recipe://local/can-ingest@1",
        "recipe_digest": hashlib.sha256(b"recipe://local/can-ingest@1").hexdigest(),
    })).stages] == ["can_ingest"]
    receipt = dataset_submit_generation(request, tmp_path / "store")
    assert submitted == [receipt.job_id]
    assert dataset_get_job(receipt.job_id, tmp_path / "store") is not None
