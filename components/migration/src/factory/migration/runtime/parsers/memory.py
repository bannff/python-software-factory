"""Parse ``memory.db`` live semantic + episodic memory (no lessons/embeddings).

Reads only committed, non-deleted rows from the trusted snapshot copy. Never
touches the ``embedding`` column, ``memory_events``, FTS tables, ``is_deleted``
rows, or ``lesson.*`` semantic keys (those belong to the lessons parser).
Schema versions outside 1–3 fail the kind. Corruption fails the kind.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..source_models import (
    MAX_TEXT_CHARS, SUPPORTED_MEMORY_VERSIONS, Diagnostic, KindReport,
    ReasonCode, SafeMemory, SourceKind, identity_of,
)
from . import build_report

_KIND = SourceKind.MEMORY


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    if not row or row[0] is None:
        raise ValueError("no schema_version")
    return int(row[0])


def _tags(raw: str | None) -> tuple[str, ...]:
    try:
        parsed = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(str(t)[:64] for t in parsed[:64] if isinstance(t, (str, int, float)))


def parse_memory(snapshot_dir: Path) -> tuple[list[SafeMemory], KindReport]:
    db_path = Path(snapshot_dir) / "memory.db"
    if not db_path.exists():
        return [], build_report(_KIND, 0, [], [])
    records: list[SafeMemory] = []
    diags: list[Diagnostic] = []
    found = 0
    try:
        conn = _connect(db_path)
    except sqlite3.DatabaseError as exc:
        return [], build_report(
            _KIND, 0, [], [Diagnostic(kind=_KIND, reason=ReasonCode.CORRUPT_DB)])
    try:
        try:
            version = _schema_version(conn)
        except (sqlite3.DatabaseError, ValueError) as exc:
            return [], build_report(
                _KIND, 0, [], [Diagnostic(kind=_KIND, reason=ReasonCode.CORRUPT_DB)])
        if version not in SUPPORTED_MEMORY_VERSIONS:
            return [], build_report(
                _KIND, 0, [], [Diagnostic(kind=_KIND, reason=ReasonCode.UNKNOWN_VERSION, detail=f"v{version}")])
        try:
            sem = conn.execute(
                "SELECT key, value_json FROM semantic_memory "
                "WHERE is_deleted=0 AND key NOT LIKE 'lesson.%'").fetchall()
            epi = conn.execute(
                "SELECT id, text, tags FROM episodic_memories WHERE is_deleted=0").fetchall()
        except sqlite3.DatabaseError as exc:
            return [], build_report(
                _KIND, 0, [], [Diagnostic(kind=_KIND, reason=ReasonCode.CORRUPT_DB)])
    finally:
        conn.close()
    for key, value_json in sem:
        found += 1
        content = "" if value_json is None else str(value_json)
        if not content or len(content) > MAX_TEXT_CHARS:
            diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.MALFORMED, detail="semantic"))
            continue
        records.append(SafeMemory(
            kind="semantic", identity=identity_of("semantic", str(key)),
            key=str(key)[:512], content=content))
    for rid, text, tags in epi:
        found += 1
        content = "" if text is None else str(text)
        if not content or len(content) > MAX_TEXT_CHARS:
            diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.MALFORMED, detail="episodic"))
            continue
        records.append(SafeMemory(
            kind="episodic", identity=identity_of("episodic", str(rid)),
            key=None, content=content, tags=_tags(tags)))
    identities = [r.identity for r in records]
    return records, build_report(_KIND, found, identities, diags)


__all__ = ["parse_memory"]
