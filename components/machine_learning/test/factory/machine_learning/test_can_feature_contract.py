"""Contract, strict materializer, and property invariants for db6ow."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from factory.machine_learning.runtime.can_feature_contract import (
    contract_artifact_bytes, create_can_feature_contract,
    load_can_feature_contract, save_can_feature_contract,
)
from factory.machine_learning.runtime.can_materializer import materialize_can_windows

from .can_contract_fixtures import contract, window


def test_training_and_inference_bytes_are_identical(tmp_path) -> None:
    feature_contract = contract(tmp_path, context=("temp_c",))
    windows = [window(feature_contract, label=1)]
    training = materialize_can_windows(windows, feature_contract)
    inference = materialize_can_windows(deepcopy(windows), feature_contract, flatten=True)
    assert inference.X.tobytes() == training.X.reshape(1, -1).tobytes()
    assert np.array_equal(training.y, inference.y)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.permutations(["label", "failure_mode", "target"]))
def test_unordered_contract_inputs_are_canonical(tmp_path, permutation) -> None:
    left = contract(tmp_path, excluded_fields=list(permutation))
    right = contract(tmp_path, excluded_fields=["target", "label", "failure_mode"])
    assert contract_artifact_bytes(left) == contract_artifact_bytes(right)
    assert left.digest == right.digest


def test_contract_binds_refs_projection_shape_and_width(tmp_path) -> None:
    value = contract(tmp_path, context=("temp_c",))
    assert value.required_shape == (2, 3) and value.required_width == 6
    assert value.ordered_columns == ("signal:a", "signal:b", "context:temp_c")
    assert value.signal_schema_ref.digest and value.prior_data_policy_ref.digest


@pytest.mark.parametrize("field,value", [
    ("required_shape", (1, 3)), ("required_width", 3),
    ("ordered_columns", ("signal:b", "signal:a")),
])
def test_contract_projection_mismatches_fail(tmp_path, field, value) -> None:
    with pytest.raises(ValueError):
        contract(tmp_path, **{field: value})


def test_contract_artifact_is_canonical_and_digest_checked(tmp_path) -> None:
    value = contract(tmp_path)
    uri = save_can_feature_contract(value, tmp_path / "contract.json")
    assert load_can_feature_contract(uri) == value
    path = tmp_path / "contract.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="canonical"):
        load_can_feature_contract(path)


_MUTATIONS = [
    "schema", "can_id", "signal_order", "context_ref", "window_size",
    "step", "grid", "cutoff", "horizon", "timesteps", "bounds_start",
    "bounds_cutoff", "bounds_end", "value_string", "value_bool", "row_width",
]


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.sampled_from(_MUTATIONS))
def test_arbitrary_mismatch_rejected_before_tensor_allocation(tmp_path, monkeypatch, mutation) -> None:
    feature_contract = contract(tmp_path)
    record = window(feature_contract)
    if mutation == "schema": record["schema_version"] = "1.0"
    elif mutation == "can_id": record["can_id"] = "0x2"
    elif mutation == "signal_order": record["signal"]["columns"].reverse()
    elif mutation == "context_ref": record["metadata"]["prior_data_policy_ref"]["digest"] = "f" * 64
    elif mutation == "window_size": record["window_size_ms"] = 21
    elif mutation == "step": record["step_size_ms"] = 21
    elif mutation == "grid": record["grid_resolution_ms"] = 5
    elif mutation == "cutoff": record["observation_cutoff_ms"] = 10
    elif mutation == "horizon": record["label_horizon_ms"] = 11
    elif mutation == "timesteps": record["num_timesteps"] = 1
    elif mutation == "bounds_start": record["bounds"]["window_start_ns"] = 1
    elif mutation == "bounds_cutoff": record["bounds"]["observation_cutoff_ns"] = 19
    elif mutation == "bounds_end": record["bounds"]["label_horizon_end_ns"] = 31
    elif mutation == "value_string": record["signal"]["values"][0][0] = "1"
    elif mutation == "value_bool": record["signal"]["values"][0][0] = True
    elif mutation == "row_width": record["signal"]["values"][0].pop()
    monkeypatch.setattr(np, "empty", lambda *_a, **_k: pytest.fail("allocated before validation"))
    with pytest.raises(ValueError):
        materialize_can_windows([record], feature_contract)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(st.floats(width=32, allow_nan=True, allow_infinity=True), min_size=4, max_size=4))
def test_numeric_domain_and_fill_semantics_are_deterministic(tmp_path, values) -> None:
    feature_contract = contract(tmp_path)
    record = window(feature_contract)
    record["signal"]["values"] = [values[:2], values[2:]]
    first = materialize_can_windows([record], feature_contract).X
    second = materialize_can_windows([deepcopy(record)], feature_contract).X
    assert first.dtype == np.float32 and first.tobytes() == second.tobytes()
