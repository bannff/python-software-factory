"""Hypothesis properties for frozen blueprints and canonical digests."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.dataset.runtime.blueprint_catalog import SCENARIO_STAGE_REF
from factory.dataset.runtime.blueprint_codec import canonical_digest, canonical_json
from factory.dataset.runtime.blueprint_models import (
    DatasetCapabilityRef,
    DatasetSourceEvidenceRef,
    DatasetStageRef,
)

from .blueprint_fixtures import blueprint


@given(reverse_evidence=st.booleans(), reverse_capabilities=st.booleans())
@settings(max_examples=50)
def test_set_like_reference_order_is_canonical(
    reverse_evidence: bool, reverse_capabilities: bool,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = blueprint(Path(directory) / "store")
    data = base.model_dump(mode="json")
    artifact = base.source_evidence[0].artifact
    data["source_evidence"].append(DatasetSourceEvidenceRef(
        id="ScenarioPack-secondary", version="1", digest="1" * 64,
        artifact=artifact,
    ).model_dump(mode="json"))
    data["capabilities"].append(DatasetCapabilityRef(
        id="secondary-capability", version="1", digest="2" * 64,
    ).model_dump(mode="json"))
    if reverse_evidence:
        data["source_evidence"].reverse()
    if reverse_capabilities:
        data["capabilities"].reverse()
    candidate = type(base).model_validate(data)
    canonical = type(base).model_validate({
        **data,
        "source_evidence": sorted(data["source_evidence"], key=lambda item: item["id"]),
        "capabilities": sorted(data["capabilities"], key=lambda item: item["id"]),
    })
    assert candidate == canonical
    assert canonical_digest(candidate) == canonical_digest(canonical)


@given(seed=st.integers(min_value=0, max_value=2**63 - 1).filter(lambda value: value != 41))
@settings(max_examples=50)
def test_semantic_mutation_changes_digest(seed: int) -> None:
    with tempfile.TemporaryDirectory() as directory:
        original = blueprint(Path(directory) / "store")
    changed = original.model_copy(update={"generation_seed": seed})
    assert canonical_digest(changed) != canonical_digest(original)


def test_stage_order_is_semantic_and_contract_is_deeply_frozen(tmp_path: Path) -> None:
    original = blueprint(tmp_path / "store")
    second = DatasetStageRef(id="second", version="1", digest="3" * 64)
    left = original.model_copy(update={"stages": (SCENARIO_STAGE_REF, second)})
    right = original.model_copy(update={"stages": (second, SCENARIO_STAGE_REF)})
    assert canonical_digest(left) != canonical_digest(right)
    with pytest.raises(ValidationError):
        original.generation_seed = 7  # type: ignore[misc]
    with pytest.raises(TypeError):
        original.stages[0] = second  # type: ignore[index]


def test_canonical_json_is_compact_utf8_and_rejects_nan() -> None:
    left = {"z": "café", "a": [1, 2]}
    right = {"a": [1, 2], "z": "café"}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_json(left) == b'{"a":[1,2],"z":"caf\xc3\xa9"}'
    assert b": " not in canonical_json(left)
    with pytest.raises(ValueError):
        canonical_json({"not-a-number": math.nan})
