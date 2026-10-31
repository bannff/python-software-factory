"""SQL schema and row projections for session persistence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..models import SessionRecord, SteerMessage

SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS companion_sessions (
  tenant_id TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  title TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  model TEXT NOT NULL,
  mode TEXT NOT NULL,
  workspace TEXT NOT NULL,
  project TEXT NOT NULL,
  origin TEXT NOT NULL,
  crew_id TEXT NOT NULL DEFAULT '',
  memory_scope TEXT NOT NULL DEFAULT '',
  pinned_rank REAL,
  tags TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT,
  active_checkpoint_id TEXT,
  pinned_message_ids TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  folder TEXT NOT NULL DEFAULT '',
  revision INTEGER NOT NULL,
  PRIMARY KEY (tenant_id, owner_id, session_id)
)
"""

SESSION_INDEX_SCHEMA = """
CREATE UNIQUE INDEX IF NOT EXISTS companion_sessions_owner_thread
ON companion_sessions (tenant_id, owner_id, thread_id)
"""

STEER_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_steers (
  tenant_id TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  delivery_id TEXT NOT NULL,
  send_id TEXT NOT NULL,
  content TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  consumed_at TEXT,
  requeued_at TEXT,
  revision INTEGER NOT NULL,
  PRIMARY KEY (tenant_id, owner_id, session_id, delivery_id),
  UNIQUE (tenant_id, owner_id, session_id, send_id)
)
"""


def columns(fields: tuple[str, ...]) -> str:
    return ", ".join(fields)


def values(fields: tuple[str, ...]) -> str:
    return ", ".join(f":{field}" for field in fields)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


SESSION_FIELDS = (
    "tenant_id", "owner_id", "session_id", "thread_id", "title", "agent_id",
    "model", "mode", "workspace", "project", "origin", "crew_id", "memory_scope",
    "pinned_rank", "tags", "created_at", "updated_at", "archived_at",
    "active_checkpoint_id", "pinned_message_ids", "summary", "folder", "revision",
)
STEER_FIELDS = (
    "tenant_id", "owner_id", "session_id", "delivery_id", "send_id", "content",
    "state", "created_at", "consumed_at", "requeued_at", "revision",
)


def params(model: SessionRecord | SteerMessage) -> dict[str, Any]:
    values = model.model_dump(mode="json")
    if isinstance(model, SessionRecord):
        values["tags"] = ",".join(model.tags)
        # JSON-encoded, not comma-joined like ``tags``: message ids are
        # opaque LangChain-generated strings with no format guarantee
        # (unlike ``SessionTag``'s own comma-excluding pattern), so a
        # naive join would risk real data corruption on an id containing
        # a comma.
        values["pinned_message_ids"] = json.dumps(list(model.pinned_message_ids))
    return values


def session_from(row: dict[str, Any] | None) -> SessionRecord | None:
    if row is None:
        return None
    values = dict(row)
    values["tags"] = tuple(filter(None, str(values.get("tags") or "").split(",")))
    raw_pins = values.get("pinned_message_ids") or "[]"
    try:
        values["pinned_message_ids"] = tuple(json.loads(str(raw_pins)))
    except (ValueError, TypeError):
        values["pinned_message_ids"] = ()
    return SessionRecord.model_validate(values)


def steer_from(row: dict[str, Any] | None) -> SteerMessage | None:
    return SteerMessage.model_validate(row) if row is not None else None


# Backward-compatible additive columns for pre-M6.5 session tables.
SESSION_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("crew_id", "TEXT NOT NULL DEFAULT ''"),
    ("memory_scope", "TEXT NOT NULL DEFAULT ''"),
    ("pinned_rank", "REAL"),
    ("tags", "TEXT NOT NULL DEFAULT ''"),
    ("active_checkpoint_id", "TEXT"),
    ("pinned_message_ids", "TEXT NOT NULL DEFAULT ''"),
    ("summary", "TEXT NOT NULL DEFAULT ''"),
    ("folder", "TEXT NOT NULL DEFAULT ''"),
)


def migrate_sessions(sql: Any) -> None:
    """Additively backfill new binding columns on an existing table."""
    existing = {
        row["name"] for row in sql.fetch_all("PRAGMA table_info(companion_sessions)")
    }
    for name, decl in SESSION_MIGRATIONS:
        if name not in existing:
            sql.execute(f"ALTER TABLE companion_sessions ADD COLUMN {name} {decl}")


__all__ = [
    "SESSION_FIELDS", "SESSION_INDEX_SCHEMA", "SESSION_MIGRATIONS", "SESSION_SCHEMA",
    "STEER_FIELDS", "STEER_SCHEMA", "columns", "migrate_sessions", "now", "params",
    "session_from", "steer_from", "values",
]
