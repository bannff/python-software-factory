"""Lessons SQL schema and strict row projection."""
from __future__ import annotations

import json
from typing import Any

from ..models import LessonRecord

LESSON_SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
 tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, lesson_id TEXT NOT NULL,
 identity_key TEXT NOT NULL, rule TEXT NOT NULL, negative TEXT,
 category TEXT NOT NULL, scope TEXT NOT NULL, scope_id TEXT,
 source TEXT NOT NULL, source_ref TEXT, evidence TEXT NOT NULL,
 confidence REAL NOT NULL, status TEXT NOT NULL, superseded_ids TEXT NOT NULL,
 memory_id TEXT, memory_revision INTEGER, revision INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY (tenant_id,owner_id,lesson_id),
 UNIQUE (tenant_id,owner_id,identity_key)
)
"""
FIELDS = tuple(LessonRecord.model_fields)


def params(record: LessonRecord) -> dict[str, Any]:
    value = record.model_dump(mode="json")
    value["evidence"] = json.dumps(value["evidence"], separators=(",", ":"))
    value["superseded_ids"] = json.dumps(value["superseded_ids"], separators=(",", ":"))
    return value


def from_row(row: dict[str, Any] | None) -> LessonRecord | None:
    if row is None:
        return None
    value = dict(row)
    value["evidence"] = tuple(json.loads(value["evidence"]))
    value["superseded_ids"] = tuple(json.loads(value["superseded_ids"]))
    return LessonRecord.model_validate_json(json.dumps(value))


__all__ = ["FIELDS", "LESSON_SCHEMA", "from_row", "params"]
