"""Adversarial + property tests for the trusted source snapshot stager."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from factory.migration.runtime import source_snapshot as snap
from factory.migration.runtime.source_models import ReasonCode
from factory.migration.runtime.source_snapshot import stage_snapshot

_SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE semantic_memory (key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
    confidence REAL DEFAULT 0.5, source TEXT NOT NULL, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, is_deleted INTEGER DEFAULT 0, embedding BLOB);
CREATE TABLE episodic_memories (id TEXT PRIMARY KEY, conversation_id TEXT,
    text TEXT NOT NULL, embedding BLOB, tags TEXT DEFAULT '[]',
    importance REAL DEFAULT 0.5, created_at TEXT NOT NULL,
    last_accessed_at TEXT, is_deleted INTEGER DEFAULT 0);
CREATE TABLE memory_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL, memory_type TEXT NOT NULL, memory_key TEXT NOT NULL,
    old_value TEXT, new_value TEXT, source TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    for v in (1, 2, 3):
        conn.execute("INSERT INTO schema_version VALUES (?, '2026-01-01T00:00:00+00:00')", (v,))
    conn.commit()


def make_home(tmp_path: Path, *, wal_keep_open: bool = False):
    home = tmp_path / "crew"
    (home / "workspace" / "memory" / "history").mkdir(parents=True)
    (home / "workspace" / "memory" / "preferences.md").write_text("# prefs\nlike dark mode\n")
    (home / "workspace" / "memory" / "projects.md").write_text("# projects\nfactory\n")
    (home / "workspace" / "memory" / "history" / "2026-01-01.md").write_text("did things\n")
    # secret files that must NEVER be staged
    (home / ".local_secret").write_text("supersecret")
    (home / "token_signing.key").write_text("KEYMATERIAL")
    db = home / "memory.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    _init_db(conn)
    conn.execute(
        "INSERT INTO semantic_memory VALUES ('pref.tone','\"warm\"',1.0,'import','t','t',0,NULL)")
    conn.execute(
        "INSERT INTO episodic_memories (id,text,tags,created_at,is_deleted) "
        "VALUES ('e1','a memory','[\"tag\"]','t',0)")
    conn.commit()
    if wal_keep_open:
        return home, conn  # caller keeps rows in -wal (no checkpoint) then closes
    conn.close()
    return home, None


def test_stages_only_allowlist_never_secrets(tmp_path):
    home, _ = make_home(tmp_path)
    dest = tmp_path / "snap"
    dest.mkdir()
    manifest, errors = stage_snapshot(home, dest)
    rels = {f.rel_path for f in manifest.files}
    assert "memory.db" in rels
    assert "workspace/memory/preferences.md" in rels
    assert not any("secret" in r or r.endswith(".key") for r in rels)
    assert not (dest / ".local_secret").exists()
    assert not (dest / "token_signing.key").exists()


def test_digest_is_deterministic(tmp_path):
    home, _ = make_home(tmp_path)
    d1, d2 = tmp_path / "s1", tmp_path / "s2"
    d1.mkdir()
    d2.mkdir()
    m1, _ = stage_snapshot(home, d1)
    m2, _ = stage_snapshot(home, d2)
    assert m1.digest == m2.digest


def test_dirty_wal_rows_included_in_backup(tmp_path):
    home, conn = make_home(tmp_path, wal_keep_open=True)
    try:
        # committed-but-not-checkpointed row lives only in -wal
        conn.execute(
            "INSERT INTO semantic_memory VALUES ('pref.new','\"x\"',1.0,'import','t','t',0,NULL)")
        conn.commit()
        dest = tmp_path / "snap"
        dest.mkdir()
        stage_snapshot(home, dest)
        backup = sqlite3.connect(f"file:{dest/'memory.db'}?mode=ro", uri=True)
        rows = {r[0] for r in backup.execute("SELECT key FROM semantic_memory")}
        backup.close()
        assert "pref.new" in rows  # plain copy + immutable=1 would miss this
    finally:
        conn.close()


def test_symlink_leaf_rejected(tmp_path):
    home, _ = make_home(tmp_path)
    prefs = home / "workspace" / "memory" / "preferences.md"
    outside = tmp_path / "evil.md"
    outside.write_text("stolen")
    prefs.unlink()
    prefs.symlink_to(outside)
    dest = tmp_path / "snap"
    dest.mkdir()
    _m, errors = stage_snapshot(home, dest)
    assert ReasonCode.SYMLINK in {e.reason for e in errors}
    assert not (dest / "workspace" / "memory" / "preferences.md").exists()


def test_symlink_parent_component_rejected(tmp_path):
    home, _ = make_home(tmp_path)
    real = tmp_path / "realmem"
    real.mkdir()
    (real / "preferences.md").write_text("x")
    mem = home / "workspace" / "memory"
    # replace the 'memory' dir with a symlink
    for child in mem.iterdir():
        if child.is_file():
            child.unlink()
    import shutil
    shutil.rmtree(mem)
    mem.symlink_to(real)
    dest = tmp_path / "snap"
    dest.mkdir()
    _m, errors = stage_snapshot(home, dest)
    assert ReasonCode.SYMLINK in {e.reason for e in errors}


def test_hardlink_rejected(tmp_path):
    home, _ = make_home(tmp_path)
    prefs = home / "workspace" / "memory" / "preferences.md"
    prefs.unlink()
    target = tmp_path / "target.md"
    target.write_text("linked")
    os.link(target, prefs)  # hardlink -> st_nlink == 2
    dest = tmp_path / "snap"
    dest.mkdir()
    _m, errors = stage_snapshot(home, dest)
    assert ReasonCode.HARDLINK in {e.reason for e in errors}


def test_corrupt_db_reported(tmp_path):
    home, _ = make_home(tmp_path)
    (home / "memory.db").write_bytes(b"not a database" * 100)
    dest = tmp_path / "snap"
    dest.mkdir()
    _m, errors = stage_snapshot(home, dest)
    assert ReasonCode.CORRUPT_DB in {e.reason for e in errors}


def test_count_bound_enforced(tmp_path, monkeypatch):
    home, _ = make_home(tmp_path)
    hist = home / "workspace" / "memory" / "history"
    for i in range(6):
        (hist / f"h{i}.md").write_text(f"entry {i}")
    monkeypatch.setattr(snap, "MAX_FILES", 2)
    dest = tmp_path / "snap"
    dest.mkdir()
    manifest, errors = stage_snapshot(home, dest)
    assert len(manifest.files) <= 2
    assert ReasonCode.COUNT_EXCEEDED in {e.reason for e in errors}
