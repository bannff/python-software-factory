"""Strict auxiliary timespan extraction tests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.jsonl_to_npy import (
    convert_jsonl_windows, extract_timespans_npy,
)

from .can_contract_fixtures import contract, window


def test_returns_none_when_no_timespans_present(tmp_path: Path) -> None:
    assert extract_timespans_npy([{"num_timesteps": 2}], tmp_path) is None
    assert not any(tmp_path.iterdir())


def test_writes_exact_timespan_matrix(tmp_path: Path) -> None:
    records = [
        {"num_timesteps": 3, "timespans": [1.0, 10.0, 20.0]},
        {"num_timesteps": 3, "timespans": [1.0, 11.0, 21.0]},
    ]
    uri = extract_timespans_npy(records, tmp_path, prefix="test")
    assert uri is not None
    values = np.load(Path(uri.removeprefix("file://")), allow_pickle=False)
    assert values.shape == (2, 3)
    np.testing.assert_array_equal(values[1], [1.0, 11.0, 21.0])


@pytest.mark.parametrize("records", [
    [
        {"num_timesteps": 3, "timespans": [1.0, 2.0, 3.0]},
        {"num_timesteps": 2, "timespans": [1.0, 2.0]},
    ],
    [
        {"num_timesteps": 3, "timespans": [1.0, 2.0, 3.0]},
        {"num_timesteps": 3},
    ],
])
def test_inconsistent_timespans_fail_closed(tmp_path: Path, records) -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        extract_timespans_npy(records, tmp_path)


def test_convert_signature_remains_three_values(tmp_path: Path) -> None:
    feature_contract = contract(tmp_path)
    record = window(feature_contract)
    path = tmp_path / "windows.jsonl"
    path.write_text(json.dumps(record))
    x_uri, y_uri, info = convert_jsonl_windows(
        path, tmp_path / "out", contract=feature_contract,
    )
    assert x_uri.startswith("file://") and y_uri.startswith("file://")
    assert info["n_samples"] == 1


def test_materialization_preserves_float64_timing_artifact(tmp_path: Path) -> None:
    feature_contract = contract(tmp_path)
    record = window(feature_contract)
    expected = np.arange(1, record["num_timesteps"] + 1, dtype=np.float64)
    record["timespans"] = expected.tolist()
    path = tmp_path / "timed.jsonl"
    path.write_text(json.dumps(record))
    _, _, info = convert_jsonl_windows(
        path, tmp_path / "timed-out", contract=feature_contract,
    )
    materialized = np.load(
        Path(info["timespans_uri"].removeprefix("file://")), allow_pickle=False,
    )
    assert materialized.dtype == np.float64
    np.testing.assert_array_equal(materialized, expected.reshape(1, -1))
