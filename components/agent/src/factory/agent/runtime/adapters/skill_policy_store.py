"""Durable owner-scoped Agent skill enablement policy store (same DB as approvals)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..skill_policy import SkillPolicy, StaleSkillPolicy


class SqliteSkillPolicyStore:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS agent_skill_policies (
                tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                disabled_skills TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, owner_id))""")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get(self, tenant_id: str, owner_id: str) -> SkillPolicy:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT disabled_skills, revision FROM agent_skill_policies "
                "WHERE tenant_id=? AND owner_id=?", (tenant_id, owner_id),
            ).fetchone()
        return SkillPolicy() if row is None else SkillPolicy(
            disabled_skills=tuple(json.loads(row[0])), revision=int(row[1]),
        )

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int, *,
        disabled_skills: tuple[str, ...],
    ) -> SkillPolicy:
        candidate = SkillPolicy(disabled_skills=disabled_skills)
        encoded = json.dumps(candidate.disabled_skills, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT revision FROM agent_skill_policies WHERE tenant_id=? AND owner_id=?",
                (tenant_id, owner_id),
            ).fetchone()
            revision = 0 if current is None else int(current[0])
            if revision != expected_revision:
                conn.rollback()
                raise StaleSkillPolicy("stale skill policy")
            next_revision = revision + 1
            if current is None:
                conn.execute(
                    "INSERT INTO agent_skill_policies VALUES (?, ?, ?, ?)",
                    (tenant_id, owner_id, encoded, next_revision),
                )
            else:
                result = conn.execute(
                    "UPDATE agent_skill_policies SET disabled_skills=?, revision=? "
                    "WHERE tenant_id=? AND owner_id=? AND revision=?",
                    (encoded, next_revision, tenant_id, owner_id, revision),
                )
                if result.rowcount != 1:
                    conn.rollback()
                    raise StaleSkillPolicy("stale skill policy")
            conn.commit()
        return SkillPolicy(disabled_skills=candidate.disabled_skills, revision=next_revision)


__all__ = ["SqliteSkillPolicyStore"]
