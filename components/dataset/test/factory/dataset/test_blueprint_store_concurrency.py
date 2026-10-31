"""Deterministic concurrency regressions for immutable blueprint publication."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from factory.dataset.runtime.adapters.blueprint_store import LocalBlueprintStore
from factory.dataset.runtime.blueprint_codec import blueprint_binding

from .blueprint_fixtures import blueprint


def _publish_while_locked(root: Path, winner, contender):
    first_store = LocalBlueprintStore(root)
    second_store = LocalBlueprintStore(root)
    winner_inside = Event()
    contender_started = Event()
    original_write = first_store._write_exclusive

    def coordinated_write(path: Path, content: bytes) -> bool:
        if path.parent == first_store.content_dir:
            winner_inside.set()
            assert contender_started.wait(timeout=5)
        return original_write(path, content)

    first_store._write_exclusive = coordinated_write  # type: ignore[method-assign]

    def publish_contender():
        assert winner_inside.wait(timeout=5)
        contender_started.set()
        return second_store.publish(contender)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(first_store.publish, winner)
        second = executor.submit(publish_contender)
        return first.result(timeout=5), second.result(timeout=5)


def test_divergent_concurrent_loser_conflicts_without_orphan_content(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    winner = blueprint(source_root, seed=41)
    contender = blueprint(source_root, seed=42)
    root = tmp_path / "published"

    first, second = _publish_while_locked(root, winner, contender)

    assert first.status == "published"
    assert second.status == "conflict"
    assert second.conflict is not None
    assert second.conflict.existing_digest == blueprint_binding(winner).digest
    assert second.conflict.requested_digest == blueprint_binding(contender).digest
    contents = list((root / "blueprints" / "sha256").glob("*.json"))
    assert [path.stem for path in contents] == [blueprint_binding(winner).digest]


def test_equal_concurrent_publication_is_create_or_match(tmp_path: Path) -> None:
    value = blueprint(tmp_path / "source")
    root = tmp_path / "published"

    first, second = _publish_while_locked(root, value, value)

    assert first.status == "published"
    assert second.status == "existing"
    assert first.ref == second.ref
    assert len(list((root / "blueprints" / "sha256").glob("*.json"))) == 1
    assert len(list((root / "blueprints" / "identities").glob("*.json"))) == 1
