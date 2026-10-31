"""Failure-pattern immutability, binding diagnostics, mutation, and replay properties."""
from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from pydantic import ValidationError

from factory.dataset.runtime.adapters.dbc_catalog import LocalDbcCatalog
from factory.dataset.runtime.adapters.failure_pattern_store import LocalFailurePatternStore
from factory.dataset.runtime.dbc_parser import parse_dbc_definition
from factory.dataset.runtime.failure_pattern_apply import apply_failure_pattern
from factory.dataset.runtime.failure_pattern_binding import bind_failure_pattern
from factory.dataset.runtime.failure_pattern_models import FailurePatternDraft
from factory.dataset.runtime.failure_pattern_scenario import pattern_scenario_draft
from factory.dataset.runtime.scenario_store import LocalScenarioPackStore

from .can_intelligence_fixtures import write_catalog


def _definition(tmp_path: Path):
    dbc, _ = write_catalog(tmp_path)
    entry = LocalDbcCatalog(tmp_path).list_entries()[0]
    return parse_dbc_definition(dbc, entry.provenance,
                                catalog_id=entry.catalog_id, version=entry.version)


def _apply_kwargs(tmp_path: Path, definition, pattern) -> dict:
    profile = {"can_ids": {}}
    for message in definition.messages:
        signal_names = [signal.name for signal in message.signals]
        correlations = ([(*signal_names[:2], 1.0)] if len(signal_names) >= 2 else [])
        profile["can_ids"][f"0x{message.arbitration_id:X}"] = {
            "signals": {signal.name: {
                "min": signal.minimum, "max": signal.maximum, "delta_max": 500.0,
            } for signal in message.signals},
            "correlations": correlations,
        }
    published = LocalScenarioPackStore(tmp_path).publish(pattern_scenario_draft(pattern))
    assert published.ref is not None
    return {"constraint_schema": profile, "scenario_pack": published.ref}


def _records(count: int = 20) -> list[dict]:
    return [{
        "timestamp_ns": index * 10_000_000,
        "arbitration_id": "0x100",
        "decoded_signals": {
            "EngineSpeed": 1000.0 + index * 30,
            "CoolantTemp": 70.0 + index * 0.5,
            "VehicleSpeed": 30.0 + index,
            "ThrottleCommand": 10.0 + index * 0.75,
        },
    } for index in range(count)]


def test_store_detects_tamper_and_builtins_are_immutable() -> None:
    store = LocalFailurePatternStore()
    refs = store.list_refs()
    assert len(refs) == 3
    pattern = store.load(refs[0])
    with pytest.raises(ValidationError):
        pattern.title = "tampered"
    tampered = pattern.model_copy(update={"digest": "0" * 64})
    with pytest.raises(ValueError, match="digest mismatch"):
        LocalFailurePatternStore((tampered,))


def test_binder_reports_all_missing_roles(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    pattern = LocalFailurePatternStore().inspect("coupled-drift")
    reduced = definition.model_copy(update={"messages": (definition.messages[1],)})
    report = bind_failure_pattern(pattern, reduced)
    assert report.status == "invalid"
    assert set(report.missing_roles) == {"thermal_state", "rotational_speed"}
    assert len(report.errors) == 2


def test_unknown_transform_is_rejected_by_closed_contract() -> None:
    pattern = LocalFailurePatternStore().inspect("coupled-drift")
    body = pattern.model_dump(mode="json", exclude={"digest"})
    body["phases"][0]["transforms"][0]["kind"] = "exec_python"
    with pytest.raises(ValidationError):
        FailurePatternDraft.model_validate(body)


@pytest.mark.parametrize("pattern_id", ["coupled-drift", "response-lag", "correlation-loss"])
def test_three_patterns_mutate_two_roles_with_event_derived_labels(
    tmp_path: Path, pattern_id: str,
) -> None:
    definition = _definition(tmp_path)
    pattern = LocalFailurePatternStore().inspect(pattern_id)
    report = bind_failure_pattern(pattern, definition)
    assert report.status == "bound" and report.binding is not None
    before = _records()
    after, lineage = apply_failure_pattern(
        before, pattern, report.binding, definition, seed=17,
        **_apply_kwargs(tmp_path, definition, pattern),
    )
    changed_roles = set()
    for original, generated in zip(before, after, strict=True):
        changed = original["decoded_signals"] != generated["decoded_signals"]
        assert (generated["is_failure"] == 1) is changed
        if changed:
            event = generated["failure_event"]
            assert event["label_derivation"] == "actual_mutation"
            changed_roles.update(event["changed_roles"])
    assert len(changed_roles) >= 2
    assert lineage.pattern.pattern_id == pattern_id
    for record in after:
        for message in definition.messages:
            for signal in message.signals:
                if signal.name not in record["decoded_signals"]:
                    continue
                value = record["decoded_signals"][signal.name]
                assert signal.minimum is None or value >= signal.minimum
                assert signal.maximum is None or value <= signal.maximum


def test_replay_is_byte_identical_and_seed_changes_identity(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    pattern = LocalFailurePatternStore().inspect("correlation-loss")
    binding = bind_failure_pattern(pattern, definition).binding
    assert binding is not None
    kwargs = _apply_kwargs(tmp_path, definition, pattern)
    first = apply_failure_pattern(_records(), pattern, binding, definition, seed=5, **kwargs)
    replay = apply_failure_pattern(_records(), pattern, binding, definition, seed=5, **kwargs)
    changed = apply_failure_pattern(_records(), pattern, binding, definition, seed=6, **kwargs)
    assert first == replay
    assert first[1].output_digest != changed[1].output_digest


def test_noop_fails_before_publication(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    pattern = LocalFailurePatternStore().inspect("response-lag")
    binding = bind_failure_pattern(pattern, definition).binding
    assert binding is not None
    records = _records()
    for record in records:
        record["decoded_signals"] = {name: 1.0 for name in record["decoded_signals"]}
    with pytest.raises(ValueError, match="mutation constraint"):
        apply_failure_pattern(
            records, pattern, binding, definition, seed=1,
            **_apply_kwargs(tmp_path, definition, pattern),
        )


@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
@settings(max_examples=12, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_label_is_equivalent_to_actual_mutation_for_any_seed(
    tmp_path: Path, seed: int,
) -> None:
    definition = _definition(tmp_path)
    pattern = LocalFailurePatternStore().inspect("correlation-loss")
    binding = bind_failure_pattern(pattern, definition).binding
    assert binding is not None
    before = _records()
    after, _ = apply_failure_pattern(
        before, pattern, binding, definition, seed,
        **_apply_kwargs(tmp_path, definition, pattern),
    )
    assert all(
        (generated["is_failure"] == 1)
        is (original["decoded_signals"] != generated["decoded_signals"])
        for original, generated in zip(before, after, strict=True)
    )


def test_correlation_pattern_requires_observed_profile_relationship(tmp_path: Path) -> None:
    definition = _definition(tmp_path)
    pattern = LocalFailurePatternStore().inspect("correlation-loss")
    binding = bind_failure_pattern(pattern, definition).binding
    assert binding is not None
    kwargs = _apply_kwargs(tmp_path, definition, pattern)
    for can_profile in kwargs["constraint_schema"]["can_ids"].values():
        can_profile["correlations"] = []
    with pytest.raises(ValueError, match="requires can_profile correlation"):
        apply_failure_pattern(
            _records(), pattern, binding, definition, seed=9, **kwargs,
        )
