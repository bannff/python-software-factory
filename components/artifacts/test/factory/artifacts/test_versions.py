from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.models import ArtifactKind
from factory.artifacts.runtime.ports import ArtifactConflictError
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def lifecycle(path: Path) -> ArtifactLifecycle:
    return ArtifactLifecycle(SQLArtifactStore(SQLiteSQLStore(str(path))))


def test_update_versions_revert_and_stale_conflict(tmp_path) -> None:
    active = lifecycle(tmp_path / "a.db")
    first = active.save("t", "o", "Doc", "v1").artifact
    second = active.update(
        "t", "o", first.slug, first.revision,
        actor_kind="agent", content="v2", kind=ArtifactKind.TEXT,
    ).artifact
    assert (second.version, second.revision, second.content) == (2, 2, "v2")
    with pytest.raises(ArtifactConflictError, match="revision conflict"):
        active.update("t", "o", first.slug, 1, actor_kind="agent", content="lost")
    reverted = active.revert(
        "t", "o", first.slug, 1, second.revision, "human",
    ).artifact
    assert (reverted.version, reverted.content, reverted.kind) == (
        3, "v1", ArtifactKind.MARKDOWN,
    )
    versions = active.versions("t", "o", first.slug)
    assert [item.version for item in versions] == [3, 2, 1]
    assert [item.event_type for item in versions] == ["reverted", "updated", "created"]


def test_metadata_update_does_not_snapshot(tmp_path) -> None:
    active = lifecycle(tmp_path / "a.db")
    first = active.save("t", "o", "Doc", "v1").artifact
    updated = active.update(
        "t", "o", first.slug, first.revision,
        actor_kind="agent", description="new",
    ).artifact
    assert (updated.version, updated.revision) == (1, 2)
    assert [item.version for item in active.versions("t", "o", first.slug)] == [1]


def test_tombstone_is_opaque_and_reserves_slug(tmp_path) -> None:
    active = lifecycle(tmp_path / "a.db")
    first = active.save("t", "o", "Doc", "body").artifact
    active.tombstone("t", "o", first.slug, first.revision)
    for operation in (
        lambda: active.get("t", "o", first.slug),
        lambda: active.versions("t", "o", first.slug),
    ):
        with pytest.raises(ValueError, match="artifact_not_found"):
            operation()
    with pytest.raises(ValueError, match="artifact_not_found"):
        active.get("t", "other", first.slug)
    assert active.save("t", "o", "Doc", "new").artifact.slug == "doc-2"


def test_prune_keeps_latest_50_and_other_artifact(tmp_path) -> None:
    path = tmp_path / "a.db"
    active = lifecycle(path)
    main = active.save("t", "o", "Main", "v1").artifact
    other = active.save("t", "o", "Other", "fixed").artifact
    for index in range(2, 62):
        main = active.update(
            "t", "o", main.slug, main.revision,
            actor_kind="agent", content=f"v{index}",
        ).artifact
    versions = active.versions("t", "o", main.slug)
    assert [item.version for item in versions] == list(range(61, 11, -1))
    assert len(versions) == 50 and versions[-1].content == "v12"
    assert lifecycle(path).versions("t", "o", main.slug) == versions
    assert active.versions("t", "o", other.slug)[0].content == "fixed"
    with pytest.raises(Exception, match="artifact version retained"):
        active.store._sql.execute(
            "DELETE FROM artifact_versions WHERE tenant_id='t' AND owner_id='o' "
            "AND slug='main' AND version=12",
        )


@given(st.integers(min_value=1, max_value=65))
@settings(max_examples=12, deadline=None)
def test_prune_window_property(updates: int) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "a.db"
        active = lifecycle(path)
        record = active.save("t", "o", "Doc", "v0").artifact
        for index in range(updates):
            record = active.update(
                "t", "o", record.slug, record.revision,
                actor_kind="agent", content=f"v{index + 1}",
            ).artifact
        versions = active.versions("t", "o", record.slug)
        expected = min(50, updates + 1)
        assert len(versions) == expected
        assert versions[0].version == record.version
        assert [v.version for v in versions] == list(
            range(record.version, record.version - expected, -1)
        )
