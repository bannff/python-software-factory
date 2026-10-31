"""Contract-mandatory CAN conversion and explicit legacy opt-in tests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.jsonl_to_npy import (
    convert_jsonl_to_npy, inspect_jsonl_windows, load_jsonl_windows,
    windows_to_arrays,
)
from factory.machine_learning.runtime.adapters.legacy_can_conversion import (
    legacy_can_windows_to_arrays,
)
from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract

from .can_contract_fixtures import contract, window


@pytest.fixture
def sample(tmp_path: Path):
    feature_contract = contract(tmp_path)
    records = [window(feature_contract, label=index % 2) for index in range(4)]
    path = tmp_path / "windows.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records))
    uri = save_can_feature_contract(feature_contract, tmp_path / "contract.json")
    return path, records, feature_contract, uri


def test_load_rejects_empty_and_malformed_jsonl(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    with pytest.raises(ValueError, match="No records"):
        load_jsonl_windows(empty)
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{bad}\n")
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_jsonl_windows(bad)


def test_exact_3d_and_flattened_arrays(sample) -> None:
    _path, records, feature_contract, _uri = sample
    X, y = windows_to_arrays(records, contract=feature_contract)
    flat, flat_y = windows_to_arrays(records, layout="2d", contract=feature_contract)
    assert X.shape == (4, 2, 2) and X.dtype == np.float32
    assert flat.shape == (4, 4) and np.array_equal(y, flat_y)


def test_contract_is_required_before_any_output_write(sample, tmp_path: Path) -> None:
    path, records, _contract, _uri = sample
    with pytest.raises(ValueError, match="contract is required"):
        windows_to_arrays(records)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="contract is required"):
        convert_jsonl_to_npy(path, output)
    assert not output.exists()


def test_convert_and_inspect_use_exact_contract(sample, tmp_path: Path) -> None:
    path, _records, _contract, contract_uri = sample
    x_uri, y_uri = convert_jsonl_to_npy(path, tmp_path / "out", contract_uri=contract_uri)
    assert np.load(Path(x_uri.removeprefix("file://"))).shape == (4, 2, 2)
    assert np.load(Path(y_uri.removeprefix("file://"))).shape == (4,)
    info = inspect_jsonl_windows(path, contract_uri=contract_uri)
    assert info["n_features"] == 2
    assert info["signal_names"] == ["signal:a", "signal:b"]
    with pytest.raises(ValueError, match="max_features"):
        inspect_jsonl_windows(path, max_features=1, contract_uri=contract_uri)


def test_legacy_shape_is_only_reachable_through_explicit_api() -> None:
    legacy = [
        {"window_data": [[1.0], [2.0]], "label": 0},
        {"window_data": [[3.0], [4.0]], "label": 1},
    ]
    with pytest.raises(ValueError, match="contract is required"):
        windows_to_arrays(legacy)
    X, y = legacy_can_windows_to_arrays(legacy, layout="2d")
    assert X.shape == (2, 2) and y.tolist() == [0, 1]


@pytest.mark.parametrize("mutation", ["ragged", "string", "bool"])
def test_explicit_legacy_api_remains_strict(mutation: str) -> None:
    record = {"window_data": [[1.0], [2.0]], "label": 0}
    if mutation == "ragged": record["window_data"][1].append(3.0)
    elif mutation == "string": record["window_data"][0][0] = "1"
    else: record["window_data"][0][0] = True
    with pytest.raises(ValueError):
        legacy_can_windows_to_arrays([record])
