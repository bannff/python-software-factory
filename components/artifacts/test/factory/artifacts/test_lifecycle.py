from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.models import ArtifactKind
from factory.artifacts.runtime.ports import ArtifactConflictError
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


def lifecycle(path) -> ArtifactLifecycle:
    return ArtifactLifecycle(SQLArtifactStore(SQLiteSQLStore(str(path))))


def test_save_get_list_v1_and_restart(tmp_path) -> None:
    path = tmp_path / "artifacts.db"
    first = lifecycle(path)
    result = first.save(
        "tenant", "owner", "Quarterly Report", "body",
        kind=ArtifactKind.MARKDOWN, tags=("q3",), idempotency_key="save-1",
    )
    assert result.outcome == "created"
    assert result.artifact.slug == "quarterly-report"
    assert first.get("tenant", "owner", result.artifact.slug) == result.artifact
    assert first.store.get_version("tenant", "owner", result.artifact.slug, 1).content == "body"
    assert lifecycle(path).get("tenant", "owner", result.artifact.slug) == result.artifact


def test_owner_scoped_slugs_and_filters(tmp_path) -> None:
    active = lifecycle(tmp_path / "artifacts.db")
    a1 = active.save("t", "a", "Same Name", "a1", tags=("x",)).artifact
    a2 = active.save("t", "a", "Same Name", "a2", tags=("y",)).artifact
    b1 = active.save("t", "b", "Same Name", "b1", tags=("x",)).artifact
    assert (a1.slug, a2.slug, b1.slug) == ("same-name", "same-name-2", "same-name")
    assert active.list("t", "a", tag="x") == [a1]
    with pytest.raises(ValueError, match="artifact_not_found"):
        active.get("t", "b", "same-name-2")


def test_idempotent_save_matches_or_conflicts(tmp_path) -> None:
    active = lifecycle(tmp_path / "artifacts.db")
    first = active.save("t", "o", "Name", "body", idempotency_key="key")
    replay = active.save("t", "o", "Name", "body", idempotency_key="key")
    assert replay.outcome == "matched"
    assert replay.artifact == first.artifact
    with pytest.raises(ArtifactConflictError, match="idempotency conflict"):
        active.save("t", "o", "Name", "changed", idempotency_key="key")
    assert len(active.list("t", "o")) == 1


def test_concurrent_same_name_allocates_distinct_slugs(tmp_path) -> None:
    path = tmp_path / "artifacts.db"
    stores = [lifecycle(path), lifecycle(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(store.save, "t", "o", "Race", str(index))
                   for index, store in enumerate(stores)]
    slugs = {future.result().artifact.slug for future in futures}
    assert slugs == {"race", "race-2"}
    assert len(lifecycle(path).list("t", "o")) == 2


def test_versions_reject_mutation(tmp_path) -> None:
    active = lifecycle(tmp_path / "artifacts.db")
    active.save("t", "o", "Name", "body")
    with pytest.raises(Exception, match="artifact version immutable"):
        active.store._sql.execute(
            "UPDATE artifact_versions SET content='x' WHERE tenant_id='t'",
        )


def test_tag_filter_applies_before_pagination(tmp_path) -> None:
    active = lifecycle(tmp_path / "artifacts.db")
    active.save("t", "o", "First", "1", tags=("other",))
    wanted = active.save("t", "o", "Second", "2", tags=("wanted",)).artifact
    active.save("t", "o", "Third", "3", tags=("other",))
    assert active.list("t", "o", limit=1, offset=0, tag="wanted") == [wanted]
