"""Parse typed lessons from ``lessons.jsonl`` and legacy ``lesson.*`` rows.

JSONL lines are isolated per-line (one malformed line never poisons the file).
Legacy semantic ``lesson.*`` rows in ``memory.db`` are read and deduplicated
against the JSONL by exact normalized rule identity — JSONL wins, legacy
duplicates are excluded with a DUPLICATE diagnostic.

Legacy rows appear in two shapes depending on the KiroCrew version that wrote
them: a ``{"rule": ..., "category": ..., "negative": ...}`` object, or a bare
JSON string that IS the rule text with no wrapper object at all. Both are
normalized to the same ``SafeLesson`` shape.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..source_models import (
    MAX_TEXT_CHARS, Diagnostic, KindReport, ReasonCode, SafeLesson,
    SourceKind, identity_of,
)
from . import build_report, iter_jsonl, malformed

_KIND = SourceKind.LESSONS


def _norm(rule: str) -> str:
    return " ".join(rule.split()).lower()


def _lesson_from(obj: Any, origin: str) -> SafeLesson | None:
    if isinstance(obj, str):
        # Some KiroCrew installs store a semantic_memory lesson.* value as a
        # bare rule string (no {rule, category, negative} wrapper) — the
        # value IS the rule text. Both shapes are legitimate; normalize here.
        obj = {"rule": obj}
    if not isinstance(obj, dict):
        return None
    rule = obj.get("rule")
    if not isinstance(rule, str) or not rule.strip() or len(rule) > MAX_TEXT_CHARS:
        return None
    negative = obj.get("negative")
    if negative is not None and (not isinstance(negative, str) or len(negative) > MAX_TEXT_CHARS):
        negative = None
    category = obj.get("category")
    scope = obj.get("repo_scope") or ""
    safe_scope = str(scope)[:256] if isinstance(scope, str) else ""
    return SafeLesson(
        identity=identity_of("lesson", f"{_norm(rule)}\x00{safe_scope}"),
        rule=rule.strip(),
        category=str(category)[:64] if isinstance(category, str) else "",
        negative=negative,
        repo_scope=safe_scope,
        origin=origin,  # type: ignore[arg-type]
    )


def _legacy_rows(snapshot_dir: Path) -> list[tuple[str, Any]]:
    db_path = snapshot_dir / "memory.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.DatabaseError:
        return []
    try:
        rows = conn.execute(
            "SELECT key, value_json FROM semantic_memory "
            "WHERE is_deleted=0 AND key LIKE 'lesson.%'").fetchall()
    except sqlite3.DatabaseError:
        return []
    finally:
        conn.close()
    out: list[tuple[str, Any]] = []
    for key, value_json in rows:
        try:
            out.append((str(key), json.loads(value_json) if value_json else None))
        except (ValueError, TypeError):
            out.append((str(key), None))
    return out


def parse_lessons(snapshot_dir: Path) -> tuple[list[SafeLesson], KindReport]:
    snapshot_dir = Path(snapshot_dir)
    records: list[SafeLesson] = []
    diags: list[Diagnostic] = []
    seen: set[str] = set()
    found = 0
    jsonl_path = snapshot_dir / "lessons.jsonl"
    if jsonl_path.exists():
        for _no, _raw, parsed in iter_jsonl(jsonl_path.read_text(encoding="utf-8", errors="replace")):
            found += 1
            lesson = None if parsed is None else _lesson_from(parsed, "jsonl")
            if lesson is None:
                diags.append(malformed(_KIND, "jsonl"))
                continue
            if lesson.identity in seen:
                diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.DUPLICATE, identity=lesson.identity))
                continue
            seen.add(lesson.identity)
            records.append(lesson)
    for _key, obj in _legacy_rows(snapshot_dir):
        found += 1
        lesson = _lesson_from(obj, "legacy_semantic")
        if lesson is None:
            diags.append(malformed(_KIND, "legacy"))
            continue
        if lesson.identity in seen:
            diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.DUPLICATE, identity=lesson.identity))
            continue
        seen.add(lesson.identity)
        records.append(lesson)
    identities = [r.identity for r in records]
    return records, build_report(_KIND, found, identities, diags)


__all__ = ["parse_lessons"]
