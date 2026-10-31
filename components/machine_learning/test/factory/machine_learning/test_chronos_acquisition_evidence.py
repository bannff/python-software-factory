"""Focused Chronos acquisition-evidence and immutable-sealing tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("chronos", reason="Chronos tests require the ml group")
pytest.importorskip("peft", reason="Chronos tests require the ml group")

from factory.machine_learning.runtime import (
    chronos_acquisition, chronos_acquisition_evidence as evidence,
)
from factory.machine_learning.runtime.adapters import chronos_native, chronos_timeseries
from factory.machine_learning.runtime.adapters.chronos_identity import MODEL_REVISION
from factory.machine_learning.runtime.adapters.chronos_timeseries import (
    ChronosTimeSeriesAdapter,
)
from factory.machine_learning.runtime.passport_refs import PassportArtifactRef
from factory.machine_learning.runtime.passport_tree_seal import (
    require_read_only_tree, seal_read_only_tree,
)
from factory.machine_learning.runtime.passport_trees import chronos_backbone_artifact_ref
from factory.machine_learning.runtime.passport_validation import canonical_json
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelConfig, TimeSeriesModelType,
)


class _Config:
    _commit_hash = "0" * 40


class _Model:
    config = _Config()


class _Pipeline:
    inner_model = _Model()


def _write_valid_evidence(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    document = evidence.acquisition_document(MODEL_REVISION)
    assert set(document["packages"]) == {
        "chronos-forecasting", "huggingface-hub", "peft", "safetensors",
        "torch", "transformers",
    }
    (root / evidence.ACQUISITION_FILENAME).write_bytes(canonical_json(document))


def _write_complete_backbone(root: Path) -> None:
    _write_valid_evidence(root)
    (root / "config.json").write_text("{}")
    (root / "model.safetensors").write_bytes(b"weights")


def _write_native_staging(root: Path) -> None:
    _write_complete_backbone(root / "backbone")
    (root / "probe").mkdir()
    (root / "probe" / "probe.pt").write_bytes(b"probe")


def test_authoring_rejects_observed_commit_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="observed resolved commit"):
        evidence.write_acquisition_document(tmp_path, _Pipeline())
    assert not (tmp_path / evidence.ACQUISITION_FILENAME).exists()


@pytest.mark.parametrize("tamper", ["package", "document"])
def test_acquisition_tamper_changes_digest_and_fails_current_evidence(
    tmp_path: Path, tamper: str,
) -> None:
    backbone = tmp_path / "backbone"
    _write_complete_backbone(backbone)
    original = chronos_backbone_artifact_ref("backbone", backbone, tmp_path)
    target = backbone / evidence.ACQUISITION_FILENAME
    if tamper == "package":
        document = json.loads(target.read_bytes())
        document["packages"]["torch"] = "0"
        target.write_bytes(canonical_json(document))
        match = "package versions"
    else:
        target.write_bytes(target.read_bytes() + b"\n")
        match = "not canonical"
    changed = chronos_backbone_artifact_ref("backbone", backbone, tmp_path)
    assert changed.digest != original.digest
    with pytest.raises(ValueError, match=match):
        evidence.validate_acquisition_document(backbone)


def test_training_delegates_writable_staging_to_cas_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = ChronosTimeSeriesAdapter(storage_root=tmp_path)
    adapter._root.mkdir(parents=True, exist_ok=True)
    ref = PassportArtifactRef(
        role="backbone", uri=(tmp_path / "source").as_uri(), digest="a" * 64,
        media_type="application/vnd.amazon.chronos2.backbone",
        format="chronos2-backbone", size_bytes=0,
        identity="amazon/chronos-2", version=MODEL_REVISION,
    )

    monkeypatch.setattr(chronos_timeseries, "validate_chronos_backbone_ref", lambda *_: None)

    def copy_backbone(_ref, _root, destination: Path) -> None:
        _write_complete_backbone(destination)

    monkeypatch.setattr(chronos_timeseries, "copy_verified_artifact", copy_backbone)
    monkeypatch.setattr(chronos_timeseries, "load_local_pipeline", lambda _path: object())
    monkeypatch.setattr(chronos_timeseries, "train_probe", lambda *_args: (
        object(), {"accuracy": 1.0}, {
            "d_model": 2, "input_size": 1, "num_classes": 2,
            "scaler_mean": [0.0], "scaler_scale": [1.0],
            "adapter_mode": "frozen", "lora_config": None,
            "val_y_true": (), "val_y_pred": (), "val_y_score": (),
        },
    ))

    def save_probe(root: Path, *_args, **_kwargs) -> None:
        (root / "probe").mkdir()
        (root / "probe" / "probe.pt").write_bytes(b"probe")

    monkeypatch.setattr(chronos_timeseries, "save_probe", save_probe)
    def publish(staging: Path, durable_root: Path) -> Path:
        assert staging.stat().st_mode & 0o200
        assert (staging / "backbone" / evidence.ACQUISITION_FILENAME).is_file()
        destination = durable_root / "published"
        seal_read_only_tree(staging)
        staging.rename(destination)
        require_read_only_tree(destination)
        return destination

    monkeypatch.setattr(chronos_timeseries, "seal_content_addressed", publish)
    job = adapter.train(
        TimeSeriesModelType.chronos, "unused-X", "unused-y",
        model_config=TimeSeriesModelConfig(local_backbone_ref=ref),
    )
    require_read_only_tree(Path(job.model_path))


def test_repeated_identical_acquisition_reuses_sealed_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_ENABLE_AUTHORING_TOOLS", "1")
    monkeypatch.setattr(chronos_acquisition, "acquire_training_pipeline", object)
    monkeypatch.setattr(
        chronos_acquisition, "save_backbone",
        lambda _pipeline, path: _write_complete_backbone(path),
    )
    monkeypatch.setattr(
        chronos_acquisition, "write_acquisition_document",
        lambda path, _pipeline: _write_valid_evidence(path),
    )
    monkeypatch.setattr(chronos_acquisition, "load_local_pipeline", lambda _path: None)

    first = chronos_acquisition.acquire_chronos2_backbone(tmp_path)
    second = chronos_acquisition.acquire_chronos2_backbone(tmp_path)

    destination = Path(first.artifact.uri.removeprefix("file://"))
    assert second.artifact == first.artifact
    assert list(destination.parent.iterdir()) == [destination]
    require_read_only_tree(destination)


def test_native_cas_retry_removes_staging_and_failed_sealed_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable_root = tmp_path / "models"
    durable_root.mkdir()
    monkeypatch.setattr(chronos_native, "_derive_passport_config", lambda _path: {})
    first_staging, retry_staging = (
        durable_root / ".first.staging", durable_root / ".retry.staging",
    )
    _write_native_staging(first_staging)
    first = chronos_native.seal_content_addressed(first_staging, durable_root)
    _write_native_staging(retry_staging)
    retry = chronos_native.seal_content_addressed(retry_staging, durable_root)

    assert retry == first and not first_staging.exists() and not retry_staging.exists()
    assert not any(path.name.endswith(".staging") for path in durable_root.iterdir())
    require_read_only_tree(first)

    failure_root = tmp_path / "failed-models"
    failure_root.mkdir()
    failed_staging = failure_root / ".failed.staging"
    _write_native_staging(failed_staging)
    original_rename = Path.rename

    def fail_publication(path: Path, destination: Path) -> Path:
        if path == failed_staging:
            raise OSError("publication failed")
        return original_rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_publication)
    with pytest.raises(OSError, match="publication failed"):
        chronos_native.seal_content_addressed(failed_staging, failure_root)
    assert not failed_staging.exists()
