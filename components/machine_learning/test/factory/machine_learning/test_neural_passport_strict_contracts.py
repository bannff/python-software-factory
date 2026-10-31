"""Strict sealed-constructor and classifier-contract rejection tests."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("torch", reason="neural passport tests require the ml group")
pytest.importorskip("chronos", reason="neural passport tests require the ml group")
pytest.importorskip("peft", reason="neural passport tests require the ml group")

from factory.machine_learning.runtime.passport_native_inference import (
    _load_neural_snapshot_scores,
)
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.mcp_utils.interface import get_service, set_service

from .test_neural_passport_subprocess import _candidate


@pytest.mark.parametrize("model_type", [
    TimeSeriesModelType.lstm, TimeSeriesModelType.tcn, TimeSeriesModelType.patchtst,
    TimeSeriesModelType.chronos,
])
def test_native_artifact_shape_is_closed(tmp_path: Path, model_type: TimeSeriesModelType) -> None:
    previous = get_service("tool_invoker")
    try:
        _, candidate, _, _, _ = _candidate(tmp_path, model_type)
        path = Path(candidate.model_artifact.uri.removeprefix("file://"))
        if model_type is TimeSeriesModelType.chronos:
            assert path.name == candidate.model_artifact.digest
            assert {item.name for item in path.iterdir()} == {"backbone", "probe"}
            assert (path / "backbone" / "config.json").is_file()
            assert (path / "backbone" / "model.safetensors").is_file()
            assert (path / "probe" / "probe.pt").is_file()
        elif model_type is TimeSeriesModelType.patchtst:
            assert {item.name for item in path.iterdir()} == {
                "config.json", "model.safetensors", "factory_preprocessing.json",
            }
        else:
            assert path.is_file() and path.name == "model.pt"
    finally:
        set_service("tool_invoker", previous)


@pytest.mark.parametrize(
    "model_type", [TimeSeriesModelType.lstm, TimeSeriesModelType.tcn],
)
def test_torch_passport_rejects_type_revision_constructor_and_classes(
    tmp_path: Path, model_type: TimeSeriesModelType,
) -> None:
    previous = get_service("tool_invoker")
    try:
        _, candidate, _, X, _ = _candidate(tmp_path, model_type)
        wrong_type = (
            "tcn" if model_type is TimeSeriesModelType.lstm else "lstm"
        )
        mutations = (
            {"architecture": wrong_type},
            {"config": {**candidate.architecture.config, "architecture_revision": "bad"}},
            {"config": {**candidate.architecture.config, "constructor": {"hidden_size": 1}}},
            {"config": {**candidate.architecture.config, "class_order": [1, 0]}},
            {"config": {**candidate.architecture.config, "threshold": 0.4}},
        )
        path = Path(candidate.model_artifact.uri.removeprefix("file://"))
        for mutation in mutations:
            architecture = candidate.architecture.model_copy(update=mutation)
            altered = candidate.model_copy(update={"architecture": architecture})
            with pytest.raises(ValueError):
                _load_neural_snapshot_scores(altered, path, X)
    finally:
        set_service("tool_invoker", previous)


def test_patchtst_passport_rejects_config_classes_and_threshold(tmp_path: Path) -> None:
    previous = get_service("tool_invoker")
    try:
        _, candidate, _, X, _ = _candidate(tmp_path, TimeSeriesModelType.patchtst)
        sealed = candidate.architecture.config
        changed_hf = {**sealed["config"], "d_model": sealed["config"]["d_model"] + 1}
        mutations = (
            {**sealed, "config": changed_hf},
            {**sealed, "class_order": [1, 0]},
            {**sealed, "threshold": 0.4},
        )
        path = Path(candidate.model_artifact.uri.removeprefix("file://"))
        for config in mutations:
            architecture = candidate.architecture.model_copy(update={"config": config})
            altered = candidate.model_copy(update={"architecture": architecture})
            with pytest.raises(ValueError):
                _load_neural_snapshot_scores(altered, path, X)
    finally:
        set_service("tool_invoker", previous)
