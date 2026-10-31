"""Focused authority and replay tests for MLX pointer publication."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("mlx.core", reason="native MLX acceptance requires Apple Silicon")
pytest.importorskip("peft", reason="neural passport helpers require mlx-test")

from factory.machine_learning.runtime.adapters import mlx_artifact
from factory.machine_learning.runtime.adapters.mlx_artifact import persist_native_model
from factory.machine_learning.runtime.can_native_record import (
    publish_native_record, replay_native_record,
)
from factory.machine_learning.runtime.can_training_seal_binding import (
    require_training_model_seal,
)
from factory.machine_learning.runtime.mlx_publication import (
    require_mlx_reference, sealed_local_model_artifact_digest, verified_mlx_tree,
)

from .mlx_pointer_fixtures import mlx_pointer_case, model_args, objects


def test_verified_tree_checks_on_consumer_failure(
    mlx_pointer_case, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factory.machine_learning.runtime.mlx_pinned_tree import PinnedMlxTree

    reference = Path(mlx_pointer_case[1].model_artifact.uri.removeprefix("file://"))
    original = PinnedMlxTree.verify
    calls = []

    def observed(self):
        calls.append(self)
        return original(self)

    monkeypatch.setattr(PinnedMlxTree, "verify", observed)
    with pytest.raises(RuntimeError, match="consumer failed"):
        with verified_mlx_tree(reference):
            raise RuntimeError("consumer failed")
    assert len(calls) == 1

    def fail_on_exit(self):
        raise ValueError("exit verification failed")

    monkeypatch.setattr(PinnedMlxTree, "verify", fail_on_exit)
    with pytest.raises(ValueError, match="exit verification failed") as caught:
        with verified_mlx_tree(reference):
            raise RuntimeError("consumer failed")
    assert isinstance(caught.value.__context__, RuntimeError)


def test_replay_keeps_one_sealed_object(tmp_path: Path, mlx_pointer_case) -> None:
    root = tmp_path / "replay"
    root.mkdir()
    args = model_args(mlx_pointer_case, root)
    reference = persist_native_model(*args)
    first = require_mlx_reference(reference)[0]
    assert persist_native_model(*args) == reference
    assert objects(root) == [first]


def test_retry_adopts_exact_sealed_crash_orphan(
    tmp_path: Path, mlx_pointer_case, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "orphan"
    root.mkdir()
    args = model_args(mlx_pointer_case, root)
    publish = mlx_artifact.publish_mlx_reference
    monkeypatch.setattr(
        mlx_artifact, "publish_mlx_reference",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("crash after seal")),
    )
    with pytest.raises(RuntimeError, match="crash after seal"):
        persist_native_model(*args)
    orphan, = objects(root)
    monkeypatch.setattr(mlx_artifact, "publish_mlx_reference", publish)
    reference = persist_native_model(*args)
    assert require_mlx_reference(reference)[0] == orphan
    assert objects(root) == [orphan]


def test_native_record_pointer_keeps_shared_root_writable(
    tmp_path: Path, mlx_pointer_case,
) -> None:
    storage_root = Path(mlx_pointer_case[0])
    reference = Path(mlx_pointer_case[1].model_artifact.uri.removeprefix("file://"))
    row = {"model_path": str(reference), "job_id": "mlx-job"}
    records = storage_root / "records"
    binding = {"family": "mlx", "can_id": "0x100"}
    effect_id = "a" * 64
    published = publish_native_record(records, effect_id, binding, row)
    (reference.parent / "after-publish").write_text("writable")
    replayed = replay_native_record(records, effect_id, binding)
    (reference.parent / "after-replay").write_text("writable")
    require_training_model_seal(replayed, storage_root)
    (reference.parent / "after-binding").write_text("writable")
    assert replayed == published


def test_structural_mlx_ref_fails_without_sealing_parent(tmp_path: Path) -> None:
    reference = tmp_path / ("A" * 64)
    reference.write_bytes(b"not-an-mlx-reference")
    reference.chmod(0o400)
    with pytest.raises(ValueError, match="MLX reference"):
        sealed_local_model_artifact_digest(reference, seal_unsealed=True)
    probe = tmp_path / "still-writable"
    probe.write_text("yes")
    assert probe.read_text() == "yes"


def test_existing_reference_repairs_parent_durability(
    tmp_path: Path, mlx_pointer_case, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "durability-repair"
    root.mkdir()
    args = model_args(mlx_pointer_case, root)
    reference = persist_native_model(*args)
    synced = []
    monkeypatch.setattr(mlx_artifact, "fsync_directory", synced.append)
    assert persist_native_model(*args) == reference
    assert synced == [root]
