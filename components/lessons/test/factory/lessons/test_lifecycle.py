from __future__ import annotations

import tempfile
import string
from pathlib import Path

from hypothesis import given, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
import pytest

from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.identity import lesson_identity
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.models import LessonScope
from factory.storage.interface import StorageRuntime


def _runtime(path: Path) -> LessonLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(path))
    return LessonLifecycle(SQLLessonStore(sql))


def test_exact_replay_enriches_once_and_never_strips_negative(tmp_path) -> None:
    runtime = _runtime(tmp_path / "lessons.db")
    inserted = runtime.add("tenant", "owner", "Always cite evidence")
    assert inserted.outcome == "inserted"
    enriched = runtime.add(
        "tenant", "owner", "  always cite evidence  ",
        negative="Never invent a source", evidence=("feedback-1",),
    )
    assert enriched.outcome == "enriched"
    assert enriched.lesson.lesson_id == inserted.lesson.lesson_id
    assert enriched.lesson.negative == "Never invent a source"
    unchanged = runtime.add(
        "tenant", "owner", "ALWAYS CITE EVIDENCE",
        negative="Different clause",
    )
    assert unchanged.outcome == "unchanged"
    assert unchanged.reason == "kept_stored_clause"
    assert unchanged.lesson.negative == "Never invent a source"


def test_scope_and_owner_are_part_of_identity_and_restart(tmp_path) -> None:
    path = tmp_path / "scope.db"
    runtime = _runtime(path)
    global_lesson = runtime.add("tenant", "owner", "Use concise prose")
    persona_lesson = runtime.add(
        "tenant", "owner", "Use concise prose",
        scope=LessonScope.PERSONA, scope_id="developer",
    )
    other = runtime.add("tenant", "other", "Use concise prose")
    assert len({global_lesson.lesson.lesson_id,
                persona_lesson.lesson.lesson_id, other.lesson.lesson_id}) == 3
    restarted = _runtime(path)
    assert restarted.get(
        "tenant", "owner", global_lesson.lesson.lesson_id,
    ) == global_lesson.lesson
    assert restarted.store.get(
        "tenant", "other", global_lesson.lesson.lesson_id,
    ) is None


def test_lower_not_casefold_preserves_distinct_unicode_rules() -> None:
    first = lesson_identity("t", "o", "Maße", "global", None)
    second = lesson_identity("t", "o", "Masse", "global", None)
    assert first != second


@given(rule=st.text(
    alphabet=string.ascii_letters + " ", min_size=1, max_size=500,
).filter(lambda value: bool(value.strip())))
def test_identity_is_case_and_edge_whitespace_stable(rule: str) -> None:
    key, lesson_id = lesson_identity("tenant", "owner", rule, "global", None)
    upper_key, upper_id = lesson_identity(
        "tenant", "owner", f"  {rule.upper()}  ", "global", None,
    )
    assert key == upper_key
    assert lesson_id == upper_id


class LessonMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = _runtime(Path(self.temp.name) / "state.db")
        self.last_revision = 0
        self.lesson_id = None

    @rule()
    def replay_or_enrich(self) -> None:
        result = self.runtime.add(
            "tenant", "owner", "Remember exact identity",
            negative="Never duplicate" if self.last_revision == 0 else None,
            evidence=(f"evidence-{self.last_revision}",),
        )
        self.lesson_id = result.lesson.lesson_id
        assert result.lesson.revision >= self.last_revision
        self.last_revision = result.lesson.revision

    @invariant()
    def one_identity_one_record(self) -> None:
        records = self.runtime.list("tenant", "owner")
        assert len(records) <= 1
        if records:
            assert records[0].lesson_id == self.lesson_id
            assert records[0].revision == self.last_revision

    def teardown(self) -> None:
        self.temp.cleanup()


TestLessonMachine = LessonMachine.TestCase


def test_proposed_curation_and_removal_are_revision_fenced(tmp_path) -> None:
    from factory.lessons.runtime.lifecycle import LessonConflictError
    from factory.lessons.runtime.models import LessonSource, LessonStatus

    runtime = _runtime(tmp_path / "curation.db")
    proposed = runtime.add(
        "tenant", "owner", "Prefer verified output",
        source=LessonSource.FEEDBACK, confidence=0.7,
    ).lesson
    assert proposed.status is LessonStatus.PROPOSED
    accepted = runtime.curate(
        "tenant", "owner", proposed.lesson_id,
        proposed.revision, LessonStatus.ACCEPTED,
    )
    assert accepted.status is LessonStatus.ACCEPTED
    with pytest.raises(LessonConflictError):
        runtime.curate(
            "tenant", "owner", proposed.lesson_id,
            proposed.revision, LessonStatus.REJECTED,
        )
    with pytest.raises(ValueError, match="lesson_not_found"):
        runtime.get("tenant", "other", proposed.lesson_id)
    runtime.remove("tenant", "owner", accepted.lesson_id, accepted.revision)
    with pytest.raises(ValueError, match="lesson_not_found"):
        runtime.get("tenant", "owner", accepted.lesson_id)


def test_explicit_replay_promotes_inferred_identity_to_accepted(tmp_path) -> None:
    from factory.lessons.runtime.models import LessonSource, LessonStatus

    runtime = _runtime(tmp_path / "authority.db")
    proposed = runtime.add(
        "tenant", "owner", "Always verify the active process",
        source=LessonSource.FEEDBACK, confidence=0.6,
    ).lesson
    promoted = runtime.add(
        "tenant", "owner", " ALWAYS VERIFY THE ACTIVE PROCESS ",
        negative="Never trust another process's health response",
    )
    assert promoted.outcome == "enriched"
    assert promoted.reason == "user_authority"
    assert promoted.lesson.lesson_id == proposed.lesson_id
    assert promoted.lesson.source is LessonSource.USER_EXPLICIT
    assert promoted.lesson.status is LessonStatus.ACCEPTED
    assert promoted.lesson.confidence == 1.0

    lower = runtime.add(
        "tenant", "owner", "Always verify the active process",
        evidence=("inferred-later",),
        source=LessonSource.OUTCOME, confidence=0.9,
    )
    assert lower.outcome == "deduped"
    assert lower.reason == "higher_authority"
    assert lower.lesson.revision == promoted.lesson.revision
