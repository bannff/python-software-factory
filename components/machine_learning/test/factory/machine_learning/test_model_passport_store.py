"""Linear immutable LocalModelPassportStore behavior."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from factory.machine_learning.runtime.adapters.model_passport_store import (
    LocalModelPassportStore,
)
from factory.machine_learning.runtime.passport_codec import create_model_passport
from factory.machine_learning.runtime.passport_refs import PassportPredecessorRef
from factory.machine_learning.runtime.passport_store_models import (
    ModelPassportConflictError, ModelPassportIntegrityError,
    ModelPassportRevisionError,
)

from .passport_fixtures import passport, predecessor


def _revision(base, revision: int, prior) -> object:
    body = base.model_dump(mode="python", exclude={"passport_digest"})
    body.update({
        "passport_revision": revision, "predecessor": predecessor(prior),
        "limitations": (f"immutable revision {revision}",),
    })
    return create_model_passport(**body)


def test_publish_is_idempotent_but_same_key_different_content_conflicts(
    tmp_path: Path,
) -> None:
    store = LocalModelPassportStore(tmp_path / "registry")
    value = passport(tmp_path)
    first = store.publish(value)
    second = store.publish(value)
    assert first.status == "published" and second.status == "existing"
    assert first.ref == second.ref
    assert store.get(first.ref) == value
    assert not os.stat(Path(first.ref.uri.removeprefix("file://"))).st_mode & 0o200
    changed_body = value.model_dump(mode="python", exclude={"passport_digest"})
    changed_body["limitations"] = ("different immutable content",)
    with pytest.raises(ModelPassportConflictError):
        store.publish(create_model_passport(**changed_body))


def test_revisions_are_gap_free_linear_and_historical_reads_remain_valid(
    tmp_path: Path,
) -> None:
    store = LocalModelPassportStore(tmp_path / "registry")
    first = passport(tmp_path)
    first_ref = store.publish(first).ref
    second = _revision(first, 2, first_ref)
    second_ref = store.publish(second).ref
    assert store.get_by_model("model-1", "1", 1) == first
    assert store.get_by_model("model-1", "1", 2) == second
    body = first.model_dump(mode="python", exclude={"passport_digest"})
    body.update({
        "passport_revision": 3,
        "predecessor": PassportPredecessorRef(
            model_id="model-1", model_version="1", passport_revision=2,
            uri=second_ref.uri, digest="f" * 64,
        ),
        "limitations": ("fork",),
    })
    with pytest.raises(ModelPassportRevisionError, match="exact registered"):
        store.publish(create_model_passport(**body))


def test_revision_gap_is_rejected(tmp_path: Path) -> None:
    store = LocalModelPassportStore(tmp_path / "registry")
    first = passport(tmp_path, model_id="gap-model")
    first_ref = store.publish(first).ref
    body = first.model_dump(mode="python", exclude={"passport_digest"})
    body.update({
        "passport_revision": 3,
        "predecessor": PassportPredecessorRef(
            model_id="gap-model", model_version="1", passport_revision=2,
            uri=first_ref.uri, digest=first_ref.digest,
        ),
    })
    with pytest.raises(ModelPassportRevisionError, match="gap"):
        store.publish(create_model_passport(**body))


def test_tamper_and_stale_refs_fail_closed(tmp_path: Path) -> None:
    store = LocalModelPassportStore(tmp_path / "registry")
    publication = store.publish(passport(tmp_path))
    stale = publication.ref.model_copy(update={"digest": "f" * 64})
    with pytest.raises(ModelPassportIntegrityError, match="stale"):
        store.get(stale)
    object_path = Path(publication.ref.uri.removeprefix("file://"))
    object_path.chmod(0o644)
    object_path.write_bytes(b"tampered")
    with pytest.raises(ModelPassportIntegrityError):
        store.get_by_model("model-1", "1", 1)


def test_symlink_storage_root_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ModelPassportIntegrityError, match="symlink"):
        LocalModelPassportStore(linked)


def test_symlinked_existing_ancestor_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ModelPassportIntegrityError, match="symlink"):
        LocalModelPassportStore(linked / "nested")


def test_logical_key_race_rereads_and_types_winner(
    tmp_path: Path, monkeypatch,
) -> None:
    def race(store, loser, winner):
        install = store._install_exclusive
        inside_winner = False

        def raced(path, content):
            nonlocal inside_winner
            if path.name.endswith(".ref.json") and not inside_winner:
                inside_winner = True
                try:
                    store.publish(winner)
                finally:
                    inside_winner = False
                return False
            return install(path, content)

        monkeypatch.setattr(store, "_install_exclusive", raced)
        return store.publish(loser)

    same_root = tmp_path / "same"
    same_root.mkdir()
    same = passport(same_root)
    existing = race(LocalModelPassportStore(same_root), same, same)
    assert existing.status == "existing"

    conflict_root = tmp_path / "conflict"
    conflict_root.mkdir()
    loser = passport(conflict_root)
    body = loser.model_dump(mode="python", exclude={"passport_digest"})
    body["limitations"] = ("race winner has different content",)
    winner = create_model_passport(**body)
    with pytest.raises(ModelPassportConflictError):
        race(LocalModelPassportStore(conflict_root), loser, winner)
