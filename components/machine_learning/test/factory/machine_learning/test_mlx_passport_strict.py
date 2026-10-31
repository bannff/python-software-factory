"""Fail-closed MLX native tree, loader, and dispatch acceptance tests."""
from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mlx.core", reason="native MLX acceptance requires Apple Silicon")
pytest.importorskip("peft", reason="strict neural passport helpers require mlx-test")

import mlx.core as mx

from factory.machine_learning.runtime.adapters.can_inference import CanInferenceBridge
from factory.machine_learning.runtime.adapters.mlx_architecture import architecture_spec
from factory.machine_learning.runtime.adapters.mlx_native import (
    load_scores, passport_config, validate_unsealed_tree,
)
from factory.machine_learning.runtime.can_passport_models import sealed_config
from factory.machine_learning.runtime.passport_native_inference import _load_neural_snapshot_scores
from factory.machine_learning.runtime.durable_files import canonical_json
from factory.machine_learning.runtime.mlx_publication import require_mlx_reference
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.mcp_utils.interface import get_service, set_service

from .neural_passport_candidate import neural_candidate


@pytest.fixture(
    scope="module", params=[TimeSeriesModelType.lstm, TimeSeriesModelType.tcn],
    ids=lambda model_type: model_type.value,
)
def mlx_case(request, tmp_path_factory: pytest.TempPathFactory):
    previous = get_service("tool_invoker")
    case = neural_candidate(
        tmp_path_factory.mktemp(f"mlx-strict-{request.param.value}"),
        request.param, backend="mlx",
    )
    try:
        yield case
    finally:
        set_service("tool_invoker", previous)


def _object(reference: Path) -> Path:
    return require_mlx_reference(reference)[0]


def _writable_copy(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    for item in (destination, *destination.rglob("*")):
        item.chmod(0o700 if item.is_dir() else 0o600)
    return destination


def test_mlx_tree_rejects_write_bits_extra_files_and_weight_tamper(
    tmp_path: Path, mlx_case,
) -> None:
    root, candidate, _, _, _ = mlx_case
    reference = Path(candidate.model_artifact.uri.removeprefix("file://"))
    tree = _object(reference)
    assert passport_config(reference) == sealed_config(candidate.architecture.config)

    weights = tree / "model.safetensors"
    weights.chmod(0o600)
    try:
        with pytest.raises(ValueError, match="sealed read-only"):
            passport_config(reference)
    finally:
        weights.chmod(0o400)

    extra = _writable_copy(tree, tmp_path / "extra")
    (extra / "unexpected.bin").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="exactly two"):
        validate_unsealed_tree(extra)

    corrupted = _writable_copy(tree, tmp_path / "corrupt")
    weights = corrupted / "model.safetensors"
    payload = dict(mx.load(str(weights)))
    payload.pop(next(iter(payload)))
    mx.save_safetensors(str(weights), payload)
    with pytest.raises((ValueError, RuntimeError), match="Missing|mismatch"):
        validate_unsealed_tree(corrupted)
    assert Path(root) in reference.parents


def test_mlx_metadata_and_loader_reject_constructor_scaler_shape_and_bytes(
    tmp_path: Path, mlx_case,
) -> None:
    _, candidate, _, X, _ = mlx_case
    reference = Path(candidate.model_artifact.uri.removeprefix("file://"))
    tree = _object(reference)
    original = json.loads((tree / "factory_model.json").read_bytes())
    mutations = (
        {"framework_version": "0.31.0"},
        {"constructor": {"hidden_size": 1}},
        {"model_type": "lightgbm"},
        {"scaler_scale": [0.0, *original["scaler_scale"][1:]]},
    )
    for index, mutation in enumerate(mutations):
        altered = _writable_copy(tree, tmp_path / f"metadata-{index}")
        payload = {**original, **mutation}
        (altered / "factory_model.json").write_bytes(canonical_json(payload))
        with pytest.raises(ValueError):
            validate_unsealed_tree(altered)

    expected = sealed_config(candidate.architecture.config)
    model_type = candidate.architecture.architecture
    with pytest.raises(ValueError, match="passport architecture"):
        load_scores(reference, model_type, {**expected, "threshold": 0.4}, X)
    with pytest.raises(ValueError, match="input shape"):
        load_scores(reference, model_type, expected, X[:, :-1])
    with pytest.raises(ValueError, match="dtype"):
        load_scores(reference, model_type, expected, X.astype(np.float64))
    nonfinite = X.copy(); nonfinite[0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="dtype, or values"):
        load_scores(reference, model_type, expected, nonfinite)


def test_mlx_is_rejected_by_generic_and_wrong_framework_dispatch(mlx_case) -> None:
    _, candidate, _, X, _ = mlx_case
    tree = Path(candidate.model_artifact.uri.removeprefix("file://"))
    with pytest.raises(ValueError, match="LightGBM"):
        CanInferenceBridge(
            model_id="mlx", model_path=str(tree), model_digest="0" * 64,
            model_type="lstm", loader_id="mlx.nn.Module.load_weights",
            contract_uri="missing", contract_digest="0" * 64, can_id="1",
            required_shape=(10, 2), required_width=20,
        )
    wrong = candidate.model_copy(update={
        "architecture": candidate.architecture.model_copy(update={"framework": "torch"}),
    })
    with pytest.raises(ValueError, match="MLX passport framework"):
        _load_neural_snapshot_scores(wrong, tree, X)
    with pytest.raises(NotImplementedError, match="not supported by MLX"):
        architecture_spec(TimeSeriesModelType.lightgbm)


def test_mlx_cas_is_idempotent_mutation_addressed_and_mismatch_closed(
    tmp_path: Path, mlx_case, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_directory_rename(*_args, **_kwargs):
        raise AssertionError("MLX object directories must never be renamed")

    monkeypatch.setattr(Path, "rename", reject_directory_rename)
    from factory.machine_learning.runtime.adapters.mlx_architecture import build_model
    from factory.machine_learning.runtime.adapters.mlx_artifact import persist_native_model

    _, candidate, _, _, _ = mlx_case
    source_reference = Path(candidate.model_artifact.uri.removeprefix("file://"))
    source = _object(source_reference)
    metadata = json.loads((source / "factory_model.json").read_bytes())
    model_type = TimeSeriesModelType(metadata["model_type"])
    model = build_model(model_type, metadata["input_size"], metadata["num_classes"])
    model.load_weights(str(source / "model.safetensors"), strict=True)
    mx.eval(model.parameters())
    root = tmp_path / "cas"
    root.mkdir()
    args = (
        root, model, model_type, metadata["input_size"], metadata["window_size"],
        metadata["num_classes"], np.asarray(metadata["scaler_mean"]),
        np.asarray(metadata["scaler_scale"]),
    )
    first = persist_native_model(*args)
    first_payload = first.read_bytes()
    first_info = first.stat()
    first_object = _object(first)
    object_info = first_object.stat()
    assert first.is_file() and stat.S_IMODE(first_info.st_mode) == 0o400
    assert first_object.name.startswith(".") and first_object.name != first.name
    assert stat.S_IMODE(object_info.st_mode) == 0o500
    assert persist_native_model(*args) == first
    assert first.read_bytes() == first_payload
    assert first.stat().st_ino == first_info.st_ino
    assert _object(first).stat().st_ino == object_info.st_ino
    changed_mean = np.asarray(metadata["scaler_mean"], dtype=np.float64)
    changed_mean[0] += 1.0
    changed_args = (*args[:-2], changed_mean, args[-1])
    changed = persist_native_model(*changed_args)
    assert changed != first

    payload = json.loads(changed.read_bytes())
    changed.chmod(0o600)
    payload["object_path"] = first_object.name
    changed.write_bytes(canonical_json(payload))
    changed.chmod(0o400)
    tampered = changed.read_bytes()
    with pytest.raises(ValueError, match="exact object bytes"):
        passport_config(changed)
    with pytest.raises(ValueError, match="exact object bytes"):
        persist_native_model(*changed_args)
    assert changed.read_bytes() == tampered
    assert stat.S_IMODE(first_object.stat().st_mode) == 0o500
