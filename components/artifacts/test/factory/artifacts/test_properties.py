from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.artifacts.runtime.adapters.sql import SQLArtifactStore
from factory.artifacts.runtime.lifecycle import ArtifactLifecycle
from factory.artifacts.runtime.slug import slug_candidate, slugify
from factory.storage.runtime.adapters.sql_sqlite import SQLiteSQLStore


@given(st.text(min_size=1, max_size=200))
@settings(max_examples=80)
def test_slug_is_always_canonical_and_bounded(name: str) -> None:
    slug = slugify(name)
    assert 1 <= len(slug) <= 80
    assert slug[0].isalnum() and slug[-1].isalnum()
    assert all(ch.isdigit() or "a" <= ch <= "z" or ch == "-" for ch in slug)
    assert len({slug_candidate(slug, n) for n in range(1, 65)}) == 64


def test_many_collisions_are_monotonic_and_owner_scoped(tmp_path) -> None:
    life = ArtifactLifecycle(SQLArtifactStore(SQLiteSQLStore(str(tmp_path / "a.db"))))
    slugs = [life.save("t", "a", "Same", str(i)).artifact.slug for i in range(8)]
    assert slugs == ["same", *[f"same-{i}" for i in range(2, 9)]]
    assert life.save("t", "b", "Same", "foreign").artifact.slug == "same"
