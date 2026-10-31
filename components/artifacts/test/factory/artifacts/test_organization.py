from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.organization import OrganizationLifecycle
from factory.artifacts.runtime.ports import ArtifactConflictError
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def services(path: Path):
    store = SQLArtifactStore(SQLiteSQLStore(str(path)))
    return ArtifactLifecycle(store), OrganizationLifecycle(store)


def test_folder_isolation_cycle_and_stale_cas(tmp_path) -> None:
    _, folders = services(tmp_path / "a.db")
    root = folders.create("t", "o", "Root")
    child = folders.create("t", "o", "Child", root.id)
    assert folders.list("t", "other") == []
    with pytest.raises(ValueError, match="not_found_or_conflict"):
        folders.create("t", "other", "Leak", root.id)
    with pytest.raises(ArtifactConflictError, match="move conflict"):
        folders.move("t", "o", root.id, root.revision, child.id)
    unchanged = folders.list("t", "o")[0]
    assert unchanged.id == root.id and unchanged.parent_id is None
    assert unchanged.revision == root.revision
    renamed = folders.rename("t", "o", child.id, child.revision, "Renamed")
    with pytest.raises(ArtifactConflictError, match="revision conflict"):
        folders.rename("t", "o", child.id, child.revision, "Lost")
    assert renamed.path == "Root/Renamed"


def test_safe_delete_reparents_children_and_artifacts(tmp_path) -> None:
    artifacts, folders = services(tmp_path / "a.db")
    root = folders.create("t", "o", "Root")
    middle = folders.create("t", "o", "Middle", root.id)
    leaf = folders.create("t", "o", "Leaf", middle.id)
    artifact = artifacts.save("t", "o", "Doc", "body").artifact
    artifact = folders.move_artifact(
        "t", "o", artifact.slug, artifact.revision, middle.id,
    )
    folders.delete("t", "o", middle.id, middle.revision)
    remaining = {item.id: item for item in folders.list("t", "o")}
    assert remaining[leaf.id].parent_id == root.id
    assert remaining[leaf.id].path == "Root/Leaf"
    reopened = artifacts.get("t", "o", artifact.slug)
    assert reopened.folder_id == root.id
    assert reopened.version == 1 and reopened.revision == artifact.revision + 1


def test_depth_twenty_is_allowed_and_twenty_one_rejected(tmp_path) -> None:
    _, folders = services(tmp_path / "a.db")
    parent = None
    for index in range(20):
        parent = folders.create("t", "o", f"Level {index}", parent).id
    assert folders.list("t", "o")[-1].depth == 20
    with pytest.raises(ValueError, match="not_found_or_conflict"):
        folders.create("t", "o", "Too deep", parent)


@given(st.integers(min_value=1, max_value=20))
@settings(max_examples=10, deadline=None)
def test_folder_depth_property(depth: int) -> None:
    with tempfile.TemporaryDirectory() as directory:
        _, folders = services(Path(directory) / "a.db")
        parent = None
        for index in range(depth):
            parent = folders.create("t", "o", f"F{index}", parent).id
        rows = folders.list("t", "o")
        assert [row.depth for row in rows] == list(range(1, depth + 1))
        assert rows[-1].id == parent


def test_concurrent_duplicate_folder_name_has_one_winner(tmp_path) -> None:
    path = tmp_path / "a.db"
    _, folders = services(path)
    workers = [services(path)[1], services(path)[1]]
    def create(index: int):
        try:
            return workers[index].create("t", "o", "Unique")
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert sum(result is not None for result in results) == 1
    assert [row.name for row in folders.list("t", "o")] == ["Unique"]


def test_folder_cap_and_moved_subtree_depth_are_bounded(tmp_path) -> None:
    _, folders = services(tmp_path / "a.db")
    destination = None
    for index in range(10):
        destination = folders.create("t", "o", f"Dest {index}", destination).id
    subtree_root = folders.create("t", "o", "Subtree")
    parent = subtree_root.id
    for index in range(10):
        parent = folders.create("t", "o", f"Child {index}", parent).id
    with pytest.raises(ArtifactConflictError, match="move conflict"):
        folders.move("t", "o", subtree_root.id, subtree_root.revision, destination)

    _, capped = services(tmp_path / "cap.db")
    capped.store._sql.execute(
        "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<500) "
        "INSERT INTO artifact_folders SELECT 't','o',printf('%032x',x),NULL,"
        "'F'||x,x,1,:now,:now,NULL FROM n",
        {"now": "2026-01-01T00:00:00+00:00"},
    )
    with pytest.raises(ValueError, match="not_found_or_conflict"):
        capped.create("t", "o", "Over cap")
