"""Canonical ScenarioPack contract and digest properties."""
from __future__ import annotations

import copy

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.dataset.runtime.scenario_codec import (
    build_scenario_pack, scenario_pack_bytes, scenario_pack_digest,
)
from factory.dataset.runtime.scenario_models import ScenarioPackDraft

from .scenario_fixtures import draft, draft_data


@given(st.booleans(), st.booleans(), st.booleans())
@settings(max_examples=16)
def test_set_like_order_does_not_change_digest(
    reverse_top: bool, reverse_refs: bool, reverse_outcomes: bool,
) -> None:
    data = draft_data()
    if reverse_top:
        for field in ("sources", "evidence", "claims", "assumptions", "outcomes", "scenarios"):
            data[field].reverse()
    if reverse_refs:
        data["scenarios"][0]["claim_ids"].reverse()
        data["claims"][0]["evidence_ids"].reverse()
    if reverse_outcomes:
        for scenario in data["scenarios"]:
            scenario["outcome_ids"].reverse()
    assert scenario_pack_digest(ScenarioPackDraft.model_validate(data)) == scenario_pack_digest(draft())


def test_semantic_change_changes_digest_and_bytes_are_canonical() -> None:
    original = draft_data()
    changed = copy.deepcopy(original)
    changed["outcomes"][0]["definition"] = "Changed outcome"
    first = build_scenario_pack(ScenarioPackDraft.model_validate(original))
    second = build_scenario_pack(ScenarioPackDraft.model_validate(changed))
    assert first.digest != second.digest
    content = scenario_pack_bytes(first)
    assert content.endswith(b"}")
    assert b'": ' not in content and b", " not in content


@pytest.mark.parametrize(
    ("field", "value"),
    [("license", ""), ("version", ""), ("digest", "A" * 64)],
)
def test_source_metadata_is_strict(field: str, value: str) -> None:
    data = draft_data()
    data["sources"][0][field] = value
    with pytest.raises(ValidationError):
        ScenarioPackDraft.model_validate(data)


def test_ranges_and_identity_are_fail_closed() -> None:
    data = draft_data()
    data["identity"] = "../escape"
    with pytest.raises(ValidationError):
        ScenarioPackDraft.model_validate(data)
    data = draft_data()
    data["evidence"][0]["range_end"] = data["evidence"][0]["range_start"]
    with pytest.raises(ValidationError):
        ScenarioPackDraft.model_validate(data)


def test_frozen_contract_is_deeply_immutable() -> None:
    pack = build_scenario_pack(draft())
    with pytest.raises(ValidationError):
        pack.version = "2.0"  # type: ignore[misc]
    assert isinstance(pack.sources, tuple)
    assert isinstance(pack.scenarios[0].outcome_ids, tuple)
