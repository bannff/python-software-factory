"""Tests for memory.db and lessons parsers (kirocrew-v1)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from factory.migration.runtime.parsers.lessons import parse_lessons
from factory.migration.runtime.parsers.memory import parse_memory
from factory.migration.runtime.source_models import ReasonCode

_SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE semantic_memory (key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
    confidence REAL DEFAULT 0.5, source TEXT NOT NULL, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, is_deleted INTEGER DEFAULT 0, embedding BLOB);
CREATE TABLE episodic_memories (id TEXT PRIMARY KEY, conversation_id TEXT,
    text TEXT NOT NULL, embedding BLOB, tags TEXT DEFAULT '[]',
    importance REAL DEFAULT 0.5, created_at TEXT NOT NULL,
    last_accessed_at TEXT, is_deleted INTEGER DEFAULT 0);
"""


def build_db(path: Path, versions=(1, 2, 3)) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    for v in versions:
        conn.execute("INSERT INTO schema_version VALUES (?, 't')", (v,))
    conn.execute(
        "INSERT INTO semantic_memory VALUES ('pref.tone','\"warm\"',1.0,'i','t','t',0,X'0102')")
    conn.execute(
        "INSERT INTO semantic_memory VALUES ('pref.gone','\"x\"',1.0,'i','t','t',1,NULL)")
    conn.execute(
        "INSERT INTO semantic_memory VALUES "
        "('lesson.abc','{\"rule\":\"legacy rule\",\"category\":\"pref\"}',1.0,'i','t','t',0,NULL)")
    conn.execute(
        "INSERT INTO episodic_memories (id,text,tags,created_at,is_deleted) "
        "VALUES ('e1','recall this','[\"a\",\"b\"]','t',0)")
    conn.execute(
        "INSERT INTO episodic_memories (id,text,tags,created_at,is_deleted) "
        "VALUES ('e2','deleted one','[]','t',1)")
    conn.commit()
    conn.close()


def test_memory_reads_live_semantic_and_episodic_only(tmp_path):
    build_db(tmp_path / "memory.db")
    records, report = parse_memory(tmp_path)
    keys = {r.key for r in records if r.kind == "semantic"}
    epi = [r for r in records if r.kind == "episodic"]
    assert "pref.tone" in keys
    assert "pref.gone" not in keys  # is_deleted
    assert "lesson.abc" not in keys  # lessons excluded from memory
    assert len(epi) == 1 and epi[0].content == "recall this"
    assert epi[0].tags == ("a", "b")
    assert report.eligible == len(records)


def test_memory_unknown_version_fails_kind(tmp_path):
    build_db(tmp_path / "memory.db", versions=(99,))
    records, report = parse_memory(tmp_path)
    assert records == []
    assert ReasonCode.UNKNOWN_VERSION in {d.reason for d in report.diagnostics}


def test_memory_corrupt_db_reported(tmp_path):
    (tmp_path / "memory.db").write_bytes(b"garbage" * 50)
    records, report = parse_memory(tmp_path)
    assert records == []
    assert ReasonCode.CORRUPT_DB in {d.reason for d in report.diagnostics}


def test_memory_missing_db_is_empty(tmp_path):
    records, report = parse_memory(tmp_path)
    assert records == [] and report.found == 0


def test_lessons_jsonl_and_legacy_dedup(tmp_path):
    build_db(tmp_path / "memory.db")
    # legacy row has rule "legacy rule"; jsonl repeats it with different spacing/case
    (tmp_path / "lessons.jsonl").write_text(
        '{"rule":"always test","category":"pref","negative":null,"repo_scope":"repo"}\n'
        '{"rule":"  LEGACY   Rule ","category":"pref"}\n'
        'not json at all\n'
    )
    records, report = parse_lessons(tmp_path)
    rules = {r.rule for r in records}
    assert "always test" in rules
    origins = {r.origin for r in records}
    assert "jsonl" in origins
    # the legacy semantic "legacy rule" is a normalized duplicate of the jsonl line
    assert ReasonCode.DUPLICATE in {d.reason for d in report.diagnostics}
    assert ReasonCode.MALFORMED in {d.reason for d in report.diagnostics}


def test_lessons_identity_normalizes_whitespace_and_case(tmp_path):
    (tmp_path / "lessons.jsonl").write_text(
        '{"rule":"Do The Thing"}\n{"rule":"do   the   thing"}\n'
    )
    records, report = parse_lessons(tmp_path)
    assert len(records) == 1  # second is a normalized duplicate
    assert ReasonCode.DUPLICATE in {d.reason for d in report.diagnostics}


def test_lessons_missing_files_empty(tmp_path):
    records, report = parse_lessons(tmp_path)
    assert records == [] and report.found == 0


def test_lessons_legacy_bare_string_value_is_the_rule_text(tmp_path):
    """Some KiroCrew installs write ``lesson.*`` values as a bare JSON string
    (no {rule, category, negative} wrapper) — the string IS the rule. Found
    live: 44 of 49 real lesson rows in one owner's memory.db used this shape;
    without this normalization every one of them was excluded as malformed."""
    db_path = tmp_path / "memory.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO semantic_memory VALUES "
        "('lesson.bare','\"Never touch main directly.\"',1.0,'i','t','t',0,NULL)")
    conn.commit()
    conn.close()
    records, report = parse_lessons(tmp_path)
    rules = {r.rule for r in records}
    assert "Never touch main directly." in rules
    bare = next(r for r in records if r.rule == "Never touch main directly.")
    assert bare.origin == "legacy_semantic"
    assert report.excluded == 0


def test_lessons_identity_includes_repository_scope(tmp_path):
    (tmp_path / "lessons.jsonl").write_text(
        '{"rule":"Always test","repo_scope":"repo-a"}\n'
        '{"rule":"Always test","repo_scope":"repo-b"}\n'
    )
    records, report = parse_lessons(tmp_path)
    assert len(records) == 2
    assert len({record.identity for record in records}) == 2
    assert report.excluded == 0
